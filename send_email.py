#!/usr/bin/env python3
"""Send a plain-text email via Gmail API using gmail-mcp OAuth tokens.

Same authentication and send path as the MCP server's send_email tool.
Run from the gmail-mcp repo root (use venv Python if you use a venv).

Examples:
  ./venv/bin/python send_email.py --to user@example.com --subject Hi --body "Hello"
  ./venv/bin/python send_email.py --to user@example.com --subject Notes --body-file report.txt
  echo "Hello" | ./venv/bin/python send_email.py --to user@example.com --subject Hi
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from email.mime.text import MIMEText

from googleapiclient.discovery import build

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from auth import get_credentials  # noqa: E402


def load_config() -> dict:
    path = os.path.join(_SCRIPT_DIR, "config.json")
    if not os.path.exists(path):
        print(f"Error: config.json not found at {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def send_plain(service, from_account: str, config: dict, to: str, subject: str, body: str) -> dict:
    mime = MIMEText(body)
    mime["to"] = to
    display_name = config.get("accounts", {}).get(from_account, {}).get("display_name")
    mime["from"] = f'{display_name} <{from_account}>' if display_name else from_account
    mime["subject"] = subject
    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
    return service.users().messages().send(userId="me", body={"raw": raw}).execute()


def main() -> None:
    parser = argparse.ArgumentParser(description="Send plain-text email via gmail-mcp OAuth")
    parser.add_argument("--to", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body", default=None, help="Plain-text body; if omitted, read stdin")
    parser.add_argument("--body-file", dest="body_file", default=None, help="Read body from file (UTF-8)")
    parser.add_argument(
        "--account",
        default=None,
        help="From-account email (default: default_account in config.json)",
    )
    args = parser.parse_args()

    config = load_config()
    account = args.account or config.get("default_account")
    if not account:
        print("Error: no --account and no default_account in config.json", file=sys.stderr)
        sys.exit(1)

    if args.body_file:
        with open(args.body_file, encoding="utf-8") as f:
            body = f.read()
    elif args.body is not None:
        body = args.body
    else:
        body = sys.stdin.read()

    if not body.strip():
        print("Error: empty body", file=sys.stderr)
        sys.exit(1)

    creds = get_credentials(account)
    service = build("gmail", "v1", credentials=creds)
    send_plain(service, account, config, args.to, args.subject, body)
    print(f"Sent to {args.to} (from {account}) subject={args.subject!r}")


if __name__ == "__main__":
    main()
