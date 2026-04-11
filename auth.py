#!/usr/bin/env python3
"""
OAuth2 authentication for gmail-mcp.

Usage:
    python auth.py authorize <email>              - Run OAuth2 flow (opens browser)
    python auth.py authorize --headless <email>   - OAuth2 flow without auto-opening browser
    python auth.py authorize                      - Authorize the default account
    python auth.py refresh <email>                - Try to refresh token with diagnostics
    python auth.py refresh                        - Refresh the default account's token
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

def authorize_account(account_email, headless=False):
    """Run the one-time OAuth2 authorization flow for an account.

    If headless=True, prints the authorization URL for manual browser visit
    (useful when running from a CLI-only environment).
    """
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

    # Flush stdout before run_local_server so the URL prints immediately
    # (Python buffers stdout in non-interactive mode; use PYTHONUNBUFFERED=1 or -u)
    sys.stdout.flush()

    creds = flow.run_local_server(
        port=0,
        open_browser=not headless,
        authorization_prompt_message=(
            "\nOpen this URL in a browser to authorize:\n\n{url}\n\n"
            "Waiting for callback on localhost..."
        ),
    )

    with open(token_file, 'w') as f:
        f.write(creds.to_json())

    print(f"Authorization successful for {account_email}")
    print(f"Token saved to {token_file}")

def refresh_token_manually(account_email):
    """Attempt to refresh the token using a direct HTTP call for better diagnostics."""
    import urllib.request
    import urllib.parse
    import urllib.error

    config = _load_config()
    account = config.get('accounts', {}).get(account_email)
    if not account:
        raise Exception(f"Account {account_email} not found in config.json")

    token_file = _resolve_path(account['token_file'])
    if not os.path.exists(token_file):
        raise Exception(f"No token file at {token_file}")

    with open(token_file, 'r') as f:
        token_data = json.load(f)

    refresh_token = token_data.get('refresh_token')
    if not refresh_token:
        print("No refresh_token in token file. Must re-authorize.")
        return False

    client_id = token_data.get('client_id')
    client_secret = token_data.get('client_secret')
    if not client_id or not client_secret:
        # Fall back to credentials.json
        creds_file = _resolve_path(config.get('credentials_file', 'credentials.json'))
        with open(creds_file, 'r') as f:
            creds_data = json.load(f)
        installed = creds_data.get('installed', {})
        client_id = client_id or installed.get('client_id')
        client_secret = client_secret or installed.get('client_secret')

    data = urllib.parse.urlencode({
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token',
    }).encode()

    req = urllib.request.Request('https://oauth2.googleapis.com/token', data=data)
    try:
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read())
        # Update the token file with new access token
        token_data['token'] = result['access_token']
        if 'expires_in' in result:
            from datetime import datetime, timedelta, timezone
            expiry = datetime.now(timezone.utc) + timedelta(seconds=result['expires_in'])
            token_data['expiry'] = expiry.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        with open(token_file, 'w') as f:
            json.dump(token_data, f)
        print(f"Token refreshed successfully for {account_email}")
        print(f"New expiry: {token_data.get('expiry')}")
        return True
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"Refresh failed (HTTP {e.code}): {error_body}")
        error_data = json.loads(error_body) if error_body else {}
        if error_data.get('error') == 'invalid_grant':
            print("\nThe refresh token has been revoked or expired.")
            print("Possible causes:")
            print("  - User revoked access in Google Account settings")
            print("  - Token exceeded Google's 6-month inactivity limit")
            print("  - A new OAuth consent revoked the old token")
            print(f"\nTo fix: python auth.py authorize {account_email}")
            print(f"  (headless): python auth.py authorize --headless {account_email}")
        return False


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    command = sys.argv[1]

    if command == 'refresh':
        # Manual refresh with diagnostics
        if len(sys.argv) >= 3:
            email = sys.argv[2]
        else:
            config = _load_config()
            email = config.get('default_account')
            if not email:
                print("No email specified and no default_account in config.json")
                sys.exit(1)
        if not refresh_token_manually(email):
            sys.exit(1)
        return

    if command != 'authorize':
        print(__doc__.strip())
        sys.exit(1)

    headless = '--headless' in sys.argv
    remaining = [a for a in sys.argv[2:] if a != '--headless']

    if remaining:
        email = remaining[0]
    else:
        config = _load_config()
        email = config.get('default_account')
        if not email:
            print("No email specified and no default_account in config.json")
            sys.exit(1)
        print(f"Using default account: {email}")

    authorize_account(email, headless=headless)

if __name__ == '__main__':
    main()
