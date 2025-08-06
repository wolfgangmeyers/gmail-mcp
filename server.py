#!/usr/bin/env python3
"""
Gmail MCP Server - A Model Context Protocol server for Gmail IMAP operations
"""

import json
import os
import sys
import imaplib
import email
from email.header import decode_header
import asyncio

from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
import mcp.types as types

# Initialize server
server = Server("gmail-mcp")

# Global connection state
gmail_connection = {
    "imap": None,
    "email_address": None,
    "app_password": None
}

def load_config():
    """Load configuration from config.json"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                gmail_connection["email_address"] = config.get('email')
                gmail_connection["app_password"] = config.get('app_password')
                return True
        except Exception as e:
            print(f"Error loading config: {e}", file=sys.stderr)
            return False
    return False

def connect():
    """Connect to Gmail via IMAP"""
    if not gmail_connection["email_address"] or not gmail_connection["app_password"]:
        raise Exception("Email credentials not configured. Please create config.json")
    
    if gmail_connection["imap"] is None:
        gmail_connection["imap"] = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        gmail_connection["imap"].login(
            gmail_connection["email_address"], 
            gmail_connection["app_password"]
        )
    return gmail_connection["imap"]

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools"""
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
                    }
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
                        "description": "The ID of the email to read"
                    }
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
                        "description": "The ID of the email to delete"
                    }
                },
                "required": ["email_id"]
            }
        ),
        types.Tool(
            name="search_emails",
            description="Search emails using IMAP search syntax",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "IMAP search query (e.g., 'FROM \"sender@example.com\"', 'SUBJECT \"meeting\"', 'UNSEEN')"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return",
                        "default": 20
                    }
                },
                "required": ["query"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls"""
    
    if not arguments:
        arguments = {}
    
    try:
        if name == "list_emails":
            num_emails = arguments.get("num_emails", 10)
            imap = connect()
            imap.select("INBOX")
            
            status, messages = imap.search(None, "ALL")
            if status != "OK":
                return [types.TextContent(type="text", text="Failed to fetch emails")]
            
            email_ids = messages[0].split()
            latest_emails = email_ids[-num_emails:] if len(email_ids) >= num_emails else email_ids
            latest_emails.reverse()
            
            emails = []
            for email_id in latest_emails:
                status, msg_data = imap.fetch(email_id, "(RFC822)")
                if status != "OK":
                    continue
                
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                subject = decode_header(msg["Subject"])[0][0]
                if isinstance(subject, bytes):
                    subject = subject.decode()
                
                from_header = decode_header(msg["From"])[0][0]
                if isinstance(from_header, bytes):
                    from_header = from_header.decode()
                
                emails.append({
                    "id": email_id.decode(),
                    "from": from_header,
                    "subject": subject,
                    "date": msg["Date"]
                })
            
            result = {"emails": emails, "count": len(emails)}
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "read_email":
            email_id = arguments["email_id"]
            imap = connect()
            imap.select("INBOX")
            
            status, msg_data = imap.fetch(email_id.encode(), "(RFC822)")
            if status != "OK":
                return [types.TextContent(type="text", text=f"Failed to fetch email {email_id}")]
            
            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)
            
            subject = decode_header(msg["Subject"])[0][0]
            if isinstance(subject, bytes):
                subject = subject.decode()
            
            from_header = decode_header(msg["From"])[0][0]
            if isinstance(from_header, bytes):
                from_header = from_header.decode()
            
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()
                        break
            else:
                body = msg.get_payload(decode=True).decode()
            
            result = {
                "id": email_id,
                "from": from_header,
                "subject": subject,
                "date": msg["Date"],
                "body": body
            }
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        elif name == "delete_email":
            email_id = arguments["email_id"]
            imap = connect()
            imap.select("INBOX")
            
            imap.store(email_id.encode(), '+FLAGS', '\\Deleted')
            result = imap.copy(email_id.encode(), '[Gmail]/Trash')
            if result[0] == 'OK':
                imap.expunge()
                return [types.TextContent(type="text", text=f"Email {email_id} moved to trash")]
            else:
                return [types.TextContent(type="text", text="Failed to move email to trash")]
        
        elif name == "search_emails":
            query = arguments["query"]
            max_results = arguments.get("max_results", 20)
            imap = connect()
            imap.select("INBOX")
            
            status, messages = imap.search(None, query)
            if status != "OK":
                return [types.TextContent(type="text", text=f"Search failed for query: {query}")]
            
            email_ids = messages[0].split()
            if not email_ids:
                result = {"emails": [], "count": 0, "query": query}
                return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
            
            email_ids = email_ids[-max_results:] if len(email_ids) > max_results else email_ids
            email_ids.reverse()
            
            emails = []
            for email_id in email_ids:
                status, msg_data = imap.fetch(email_id, "(RFC822)")
                if status != "OK":
                    continue
                
                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                
                subject = decode_header(msg["Subject"])[0][0]
                if isinstance(subject, bytes):
                    subject = subject.decode()
                
                from_header = decode_header(msg["From"])[0][0]
                if isinstance(from_header, bytes):
                    from_header = from_header.decode()
                
                emails.append({
                    "id": email_id.decode(),
                    "from": from_header,
                    "subject": subject,
                    "date": msg["Date"]
                })
            
            result = {"emails": emails, "count": len(emails), "query": query}
            return [types.TextContent(type="text", text=json.dumps(result, indent=2))]
        
        else:
            return [types.TextContent(type="text", text=f"Unknown tool: {name}")]
    
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]

def main():
    """Main entry point"""
    # Load config on startup
    if not load_config():
        print("Warning: config.json not found or invalid. Please create it before using the server.", file=sys.stderr)
    
    # Run the server using asyncio
    asyncio.run(run_server())

async def run_server():
    """Run the MCP server"""
    async with stdio_server() as (read_stream, write_stream):
        init_options = InitializationOptions(
            server_name="gmail-mcp",
            server_version="1.0.0",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={}
            )
        )
        await server.run(read_stream, write_stream, init_options)

if __name__ == "__main__":
    main()