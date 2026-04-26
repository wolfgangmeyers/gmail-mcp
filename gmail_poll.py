#!/usr/bin/env python3
"""
Poll a Gmail account for emails from senders configured in config.json under
`allowed_senders`, relay them to the supervisor mailbox, then delete from Gmail.

Designed to run via cron every minute. Idempotent — no side effects if no new mail.
"""

import base64
import email.utils
import json
import logging
import os
import re
import subprocess
import sys

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError

SCOPES = ['https://mail.google.com/']
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.expanduser('~/.mecha-wolfgang/gmail-poll.log')
MAILBOX_SEND = os.path.expanduser('~/.claude/skills/supervisor/tools/mailbox_send.py')


def load_config():
    with open(os.path.join(PROJECT_DIR, 'config.json'), 'r') as f:
        return json.load(f)


def _poll_account(cfg):
    return cfg.get('poll_account') or cfg['default_account']


def _allowed_senders(cfg):
    return cfg.get('allowed_senders', ['wolfgangmeyers@gmail.com'])


# mailbox_send.py validates --from against r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$" and rejects
# '@'. Strip to the email local-part and replace any disallowed chars with '_' so the
# sender stays recognizable (wolfgangmeyers@gmail.com → wolfgangmeyers).
_SANITIZE_RE = re.compile(r'[^a-zA-Z0-9_-]')


def sender_address_from_header(from_header):
    """Extract bare address from a From: header (handles 'Name <addr>')."""
    _, addr = email.utils.parseaddr(from_header or '')
    return addr


def sender_to_agent_name(addr):
    """Convert email address to a mailbox agent name accepted by mailbox_send.py."""
    local = (addr or '').split('@', 1)[0]
    sanitized = _SANITIZE_RE.sub('_', local)
    if not sanitized or not sanitized[0].isalnum():
        return 'user'
    return sanitized


os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
log = logging.getLogger(__name__)


def get_credentials(config, poll_account):
    account = config['accounts'][poll_account]
    token_file = os.path.join(PROJECT_DIR, account['token_file'])

    if not os.path.exists(token_file):
        log.error(f"No token file for {poll_account}")
        sys.exit(1)

    creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(token_file, 'w') as f:
                f.write(creds.to_json())
        except RefreshError:
            log.error(f"Token expired/revoked for {poll_account}. Re-run: python auth.py authorize {poll_account}")
            sys.exit(1)

    return creds


def extract_body(msg):
    payload = msg.get('payload', {})

    if 'body' in payload and payload['body'].get('data'):
        return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='replace')

    for part in payload.get('parts', []):
        if part.get('mimeType') == 'text/plain' and part.get('body', {}).get('data'):
            return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='replace')
        for sub in part.get('parts', []):
            if sub.get('mimeType') == 'text/plain' and sub.get('body', {}).get('data'):
                return base64.urlsafe_b64decode(sub['body']['data']).decode('utf-8', errors='replace')

    return ''


def deliver_to_mailbox(sender, subject, body):
    result = subprocess.run(
        [sys.executable, MAILBOX_SEND, '--to', 'supervisor', '--from', sender, '--subject', subject, '--body', body],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        log.error(f"mailbox_send failed: {result.stderr.strip()}")
        return False
    return True


def main():
    config = load_config()
    poll_account = _poll_account(config)
    allowed_senders = _allowed_senders(config)

    # Empty allowlist would build an empty Gmail query, which matches every message.
    # Refuse to run rather than relay and delete the whole inbox.
    if not allowed_senders:
        log.error("config 'allowed_senders' resolved to empty list — refusing to poll. Fix config.json.")
        sys.exit(1)
    allowed_lower = {s.lower() for s in allowed_senders}

    creds = get_credentials(config, poll_account)
    service = build('gmail', 'v1', credentials=creds)

    query = ' OR '.join(f'from:{addr}' for addr in allowed_senders)
    results = service.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])

    if not messages:
        return

    log.info(f"Found {len(messages)} email(s) matching {allowed_senders}")

    for msg_ref in messages:
        msg = service.users().messages().get(userId='me', id=msg_ref['id'], format='full').execute()
        headers = {h['name'].lower(): h['value'] for h in msg.get('payload', {}).get('headers', [])}
        subject = headers.get('subject', '(no subject)')
        sender_addr = sender_address_from_header(headers.get('from', ''))

        # Defense-in-depth: Gmail's `from:` operator filters server-side, but re-check
        # the parsed header here so a fuzzy match never lets unauthorized mail through.
        if sender_addr.lower() not in allowed_lower:
            log.warning(f"Skipping {msg_ref['id']}: From header '{sender_addr}' not in allowed_senders")
            continue

        sender = sender_to_agent_name(sender_addr)
        body = extract_body(msg)

        log.info(f"Processing: {subject} from {sender_addr} (id={msg_ref['id']})")

        if deliver_to_mailbox(sender, subject, body):
            service.users().messages().delete(userId='me', id=msg_ref['id']).execute()
            log.info(f"Delivered and deleted: {subject} from {sender_addr} (id={msg_ref['id']})")
        else:
            log.error(f"Delivery failed, keeping email: {subject} (id={msg_ref['id']})")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log.exception(f"gmail_poll failed: {e}")
        sys.exit(1)
