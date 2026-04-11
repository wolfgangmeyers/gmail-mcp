#!/usr/bin/env python3
"""
Gmail MCP Server - A Model Context Protocol server for Gmail via REST API with OAuth2.
"""

import base64
import json
import os
import sys
import asyncio
from email.mime.text import MIMEText

from googleapiclient.discovery import build
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
import mcp.types as types

from auth import get_credentials

server = Server("gmail-mcp")

# Cached Gmail service instances per account
_services = {}
_config = None


def load_config():
    global _config
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
    if not os.path.exists(config_path):
        return False
    with open(config_path, 'r') as f:
        _config = json.load(f)
    return True


def get_service(account=None):
    """Get a Gmail API service for the given account."""
    if account is None:
        account = _config['default_account']

    if account not in _config.get('accounts', {}):
        raise Exception(f"Account {account} not found in config.json")

    if account not in _services:
        creds = get_credentials(account)
        _services[account] = build('gmail', 'v1', credentials=creds)

    return _services[account], account


def _parse_message_headers(msg):
    """Extract common headers from a Gmail API message."""
    headers = {h['name'].lower(): h['value'] for h in msg.get('payload', {}).get('headers', [])}
    return {
        'id': msg['id'],
        'threadId': msg.get('threadId', ''),
        'from': headers.get('from', ''),
        'to': headers.get('to', ''),
        'subject': headers.get('subject', ''),
        'date': headers.get('date', ''),
        'snippet': msg.get('snippet', ''),
    }


def _extract_body(msg):
    """Extract plain text body from a Gmail API message."""
    payload = msg.get('payload', {})

    # Simple message (no parts)
    if 'body' in payload and payload['body'].get('data'):
        return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='replace')

    # Multipart message
    parts = payload.get('parts', [])
    for part in parts:
        if part.get('mimeType') == 'text/plain' and part.get('body', {}).get('data'):
            return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='replace')
        # Check nested parts
        for sub in part.get('parts', []):
            if sub.get('mimeType') == 'text/plain' and sub.get('body', {}).get('data'):
                return base64.urlsafe_b64decode(sub['body']['data']).decode('utf-8', errors='replace')

    return ''


ACCOUNT_PROPERTY = {
    "account": {
        "type": "string",
        "description": "Gmail account to use (defaults to default_account from config)"
    }
}


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="list_emails",
            description="List recent emails from Gmail inbox",
            inputSchema={
                "type": "object",
                "properties": {
                    "num_emails": {
                        "type": "integer",
                        "description": "Number of recent emails to list",
                        "default": 10
                    },
                    **ACCOUNT_PROPERTY
                }
            }
        ),
        types.Tool(
            name="read_email",
            description="Read a specific email by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "The Gmail message ID"
                    },
                    **ACCOUNT_PROPERTY
                },
                "required": ["email_id"]
            }
        ),
        types.Tool(
            name="delete_email",
            description="Delete an email by moving it to trash",
            inputSchema={
                "type": "object",
                "properties": {
                    "email_id": {
                        "type": "string",
                        "description": "The Gmail message ID to delete"
                    },
                    **ACCOUNT_PROPERTY
                },
                "required": ["email_id"]
            }
        ),
        types.Tool(
            name="send_email",
            description="Send an email via Gmail",
            inputSchema={
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line"
                    },
                    "body": {
                        "type": "string",
                        "description": "Email body (plain text)"
                    },
                    **ACCOUNT_PROPERTY
                },
                "required": ["to", "subject", "body"]
            }
        ),
        types.Tool(
            name="search_emails",
            description="Search emails using Gmail search syntax (same as Gmail web UI)",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Gmail search query (e.g., 'from:sender@example.com', 'subject:meeting', 'is:unread')"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 20
                    },
                    **ACCOUNT_PROPERTY
                },
                "required": ["query"]
            }
        )
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    if not arguments:
        arguments = {}

    try:
        account = arguments.pop('account', None)
        service, account_email = get_service(account)

        if name == "list_emails":
            num_emails = arguments.get("num_emails", 10)
            results = service.users().messages().list(
                userId='me', maxResults=num_emails, labelIds=['INBOX']
            ).execute()

            messages = results.get('messages', [])
            emails = []
            for msg_ref in messages:
                msg = service.users().messages().get(
                    userId='me', id=msg_ref['id'], format='metadata',
                    metadataHeaders=['From', 'To', 'Subject', 'Date']
                ).execute()
                emails.append(_parse_message_headers(msg))

            result = {"emails": emails, "count": len(emails), "account": account_email}
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        elif name == "read_email":
            email_id = arguments["email_id"]
            msg = service.users().messages().get(
                userId='me', id=email_id, format='full'
            ).execute()

            info = _parse_message_headers(msg)
            info['body'] = _extract_body(msg)
            info['labels'] = msg.get('labelIds', [])
            return [types.TextContent(type="text", text=json.dumps(info, indent=2))]

        elif name == "delete_email":
            email_id = arguments["email_id"]
            service.users().messages().trash(userId='me', id=email_id).execute()
            return [types.TextContent(type="text", text=f"Email {email_id} moved to trash")]

        elif name == "send_email":
            to_addr = arguments["to"]
            subject = arguments["subject"]
            body = arguments["body"]

            mime = MIMEText(body)
            mime['to'] = to_addr
            display_name = _config.get('accounts', {}).get(account_email, {}).get('display_name')
            mime['from'] = f"{display_name} <{account_email}>" if display_name else account_email
            mime['subject'] = subject

            raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
            service.users().messages().send(
                userId='me', body={'raw': raw}
            ).execute()

            return [types.TextContent(type="text", text=f"Email sent to {to_addr} with subject: {subject}")]

        elif name == "search_emails":
            query = arguments["query"]
            max_results = arguments.get("max_results", 20)

            results = service.users().messages().list(
                userId='me', q=query, maxResults=max_results
            ).execute()

            messages = results.get('messages', [])
            if not messages:
                result = {"emails": [], "count": 0, "query": query, "account": account_email}
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

            emails = []
            for msg_ref in messages:
                msg = service.users().messages().get(
                    userId='me', id=msg_ref['id'], format='metadata',
                    metadataHeaders=['From', 'To', 'Subject', 'Date']
                ).execute()
                emails.append(_parse_message_headers(msg))

            result = {"emails": emails, "count": len(emails), "query": query, "account": account_email}
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]

        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]

    except Exception as e:
        # Clear cached service on auth errors so next call re-authenticates
        if 'invalid_grant' in str(e).lower() or '401' in str(e):
            _services.pop(account, None)
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


def main():
    if not load_config():
        print("Warning: config.json not found. Please create it.", file=sys.stderr)
    asyncio.run(run_server())


async def run_server():
    async with stdio_server() as (read_stream, write_stream):
        init_options = InitializationOptions(
            server_name="gmail-mcp",
            server_version="2.0.0",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={}
            )
        )
        await server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    main()
