#!/usr/bin/env python3
"""
OAuth2 authentication for gmail-mcp.

Usage:
    python auth.py authorize <email>   - Run one-time OAuth2 flow for an account
    python auth.py authorize           - Authorize the default account from config
"""

import json
import os
import sys

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google.auth.exceptions import RefreshError
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://mail.google.com/']

def _config_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')

def _load_config():
    with open(_config_path(), 'r') as f:
        return json.load(f)

def _resolve_path(relative_path):
    """Resolve a path relative to the project directory."""
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, relative_path)

def get_credentials(account_email):
    """Load and refresh credentials for an account. Returns Credentials or raises."""
    config = _load_config()

    account = config.get('accounts', {}).get(account_email)
    if not account:
        raise Exception(f"Account {account_email} not found in config.json")

    token_file = _resolve_path(account['token_file'])
    if not os.path.exists(token_file):
        raise Exception(
            f"No token file for {account_email}. "
            f"Run: python auth.py authorize {account_email}"
        )

    creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Save refreshed token
            with open(token_file, 'w') as f:
                f.write(creds.to_json())
        except RefreshError:
            raise Exception(
                f"OAuth token expired/revoked for {account_email}. "
                f"Re-run: python auth.py authorize {account_email}"
            )

    if not creds.valid:
        raise Exception(
            f"Invalid credentials for {account_email}. "
            f"Re-run: python auth.py authorize {account_email}"
        )

    return creds

def authorize_account(account_email):
    """Run the one-time OAuth2 authorization flow for an account."""
    config = _load_config()

    account = config.get('accounts', {}).get(account_email)
    if not account:
        raise Exception(f"Account {account_email} not found in config.json")

    credentials_file = _resolve_path(config.get('credentials_file', 'credentials.json'))
    if not os.path.exists(credentials_file):
        raise Exception(f"credentials.json not found at {credentials_file}")

    token_file = _resolve_path(account['token_file'])

    # Ensure tokens directory exists
    os.makedirs(os.path.dirname(token_file), exist_ok=True)

    flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(token_file, 'w') as f:
        f.write(creds.to_json())

    print(f"Authorization successful for {account_email}")
    print(f"Token saved to {token_file}")

def main():
    if len(sys.argv) < 2 or sys.argv[1] != 'authorize':
        print(__doc__.strip())
        sys.exit(1)

    if len(sys.argv) >= 3:
        email = sys.argv[2]
    else:
        config = _load_config()
        email = config.get('default_account')
        if not email:
            print("No email specified and no default_account in config.json")
            sys.exit(1)
        print(f"Using default account: {email}")

    authorize_account(email)

if __name__ == '__main__':
    main()
