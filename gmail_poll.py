#!/usr/bin/env python3
"""
Poll skraaglenax@gmail.com for emails from wolfgangmeyers@gmail.com,
relay them to the supervisor mailbox, then delete from Gmail.

Designed to run via cron every minute. Idempotent — no side effects if no new mail.
"""

import base64
import json
import logging
import os
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

def _load_poll_account():
    with open(os.path.join(PROJECT_DIR, 'config.json'), 'r') as f:
        cfg = json.load(f)
    return cfg.get('poll_account') or cfg['default_account']


def _load_from_filters():
    with open(os.path.join(PROJECT_DIR, 'config.json'), 'r') as f:
        cfg = json.load(f)
    return cfg.get('from_filters') or ['wolfgangmeyers@gmail.com']


POLL_ACCOUNT = _load_poll_account()
FROM_FILTERS = _load_from_filters()

# Set up logging
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
)
log = logging.getLogger(__name__)


def load_config():
    with open(os.path.join(PROJECT_DIR, 'config.json'), 'r') as f:
        return json.load(f)


def get_credentials(config):
    account = config['accounts'][POLL_ACCOUNT]
    token_file = os.path.join(PROJECT_DIR, account['token_file'])

    if not os.path.exists(token_file):
        log.error(f"No token file for {POLL_ACCOUNT}")
        sys.exit(1)

    creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(token_file, 'w') as f:
                f.write(creds.to_json())
        except RefreshError:
            log.error(f"Token expired/revoked for {POLL_ACCOUNT}. Re-run: python auth.py authorize {POLL_ACCOUNT}")
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


def deliver_to_mailbox(subject, body):
    result = subprocess.run(
        [sys.executable, MAILBOX_SEND, '--to', 'supervisor', '--from', 'user', '--subject', subject, '--body', body],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        log.error(f"mailbox_send failed: {result.stderr.strip()}")
        return False
    return True


def main():
    config = load_config()
    creds = get_credentials(config)
    service = build('gmail', 'v1', credentials=creds)

    query = ' OR '.join(f'from:{addr}' for addr in FROM_FILTERS)
    results = service.users().messages().list(userId='me', q=query).execute()
    messages = results.get('messages', [])

    if not messages:
        return

    log.info(f"Found {len(messages)} email(s) matching {FROM_FILTERS}")

    for msg_ref in messages:
        msg = service.users().messages().get(userId='me', id=msg_ref['id'], format='full').execute()
        headers = {h['name'].lower(): h['value'] for h in msg.get('payload', {}).get('headers', [])}
        subject = headers.get('subject', '(no subject)')
        body = extract_body(msg)

        log.info(f"Processing: {subject} (id={msg_ref['id']})")

        if deliver_to_mailbox(subject, body):
            service.users().messages().delete(userId='me', id=msg_ref['id']).execute()
            log.info(f"Delivered and deleted: {subject} (id={msg_ref['id']})")
        else:
            log.error(f"Delivery failed, keeping email: {subject} (id={msg_ref['id']})")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log.exception(f"gmail_poll failed: {e}")
        sys.exit(1)
