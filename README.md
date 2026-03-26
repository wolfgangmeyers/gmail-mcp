# Gmail MCP Server

A Model Context Protocol (MCP) server that provides Claude with access to Gmail via the Gmail REST API with OAuth2 authentication.

## Features

- List recent emails from inbox
- Read full email contents
- Send emails
- Search emails (Gmail search syntax)
- Delete emails (move to trash)
- Multi-account support

## Setup from Scratch

### Prerequisites

- Python 3.10+
- A Google account with Gmail
- A Google Cloud project (or willingness to create one)

### Step 1: Install dependencies

```bash
git clone <repo-url>
cd gmail-mcp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Step 2: Google Cloud project setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. **Create a new project** (e.g., "gmail-mcp")
3. **Enable the Gmail API**:
   - Navigate to APIs & Services > Library
   - Search for "Gmail API" and click Enable
4. **Configure OAuth consent screen**:
   - Navigate to Google Auth Platform > Overview > Get Started (or Branding)
   - App name: `gmail-mcp`
   - User support email: your email
   - Audience: **External**, testing mode
   - Contact email: your email
   - Click Create
5. **Add test users** (required for testing mode):
   - Navigate to Google Auth Platform > Audience
   - Under "Test users", click "+ Add users"
   - Add each Gmail address you want to use
6. **Create OAuth2 credentials**:
   - Navigate to Google Auth Platform > Clients > Create Client
   - Application type: **Desktop app**
   - Name: `gmail-mcp` (or any name)
   - Click Create
   - **Download the JSON** — save it as `credentials.json` in the project root

### Step 3: Configure accounts

Copy the example config and edit:

```bash
cp config.example.json config.json
```

Edit `config.json`:

```json
{
  "accounts": {
    "you@gmail.com": {
      "token_file": "tokens/you.json"
    }
  },
  "default_account": "you@gmail.com",
  "credentials_file": "credentials.json"
}
```

Add multiple accounts by adding entries to the `accounts` map.

### Step 4: Authorize accounts

Run the authorization flow for each account:

```bash
source venv/bin/activate
python auth.py authorize you@gmail.com
```

This opens a browser window. Sign in with the Gmail account, click through the consent screen ("This app isn't verified" — click Continue), and grant access. The token is saved to the `tokens/` directory.

Repeat for each account in your config.

### Step 5: Add to Claude Code

```bash
claude mcp add gmail-mcp "/path/to/gmail-mcp/run_mcp.sh"
```

Or directly:

```bash
claude mcp add gmail-mcp "/path/to/gmail-mcp/venv/bin/python /path/to/gmail-mcp/server.py"
```

## Usage

All tools accept an optional `account` parameter to specify which Gmail account to use. If omitted, the `default_account` from config is used.

### Tools

| Tool | Description | Required params |
|---|---|---|
| `list_emails` | List recent inbox emails | `num_emails` (optional, default 10) |
| `read_email` | Read full email by ID | `email_id` |
| `send_email` | Send an email | `to`, `subject`, `body` |
| `search_emails` | Search with Gmail syntax | `query`, `max_results` (optional) |
| `delete_email` | Move email to trash | `email_id` |

### Search query examples

Uses Gmail's native search syntax (same as the Gmail web UI):

- `from:sender@example.com` — emails from a sender
- `subject:meeting` — emails with "meeting" in subject
- `is:unread` — unread emails
- `after:2025/01/01` — emails after a date
- `has:attachment` — emails with attachments
- `label:important` — emails with a label

## Token Expiry

OAuth tokens in **testing mode** expire after 7 days. When this happens, the server returns a clear error message. Re-run the authorization flow:

```bash
python auth.py authorize you@gmail.com
```

## Security

- `credentials.json`, `config.json`, and `tokens/` are gitignored
- Never commit OAuth credentials or tokens to version control
- Tokens can be revoked anytime from [Google Account Permissions](https://myaccount.google.com/permissions)

## Project Structure

```
gmail-mcp/
├── server.py              # MCP server (Gmail REST API + OAuth2)
├── auth.py                # OAuth2 flow and credential management
├── config.json            # Account configuration (gitignored)
├── config.example.json    # Example configuration
├── credentials.json       # OAuth client credentials from GCP (gitignored)
├── tokens/                # Per-account OAuth tokens (gitignored)
├── requirements.txt       # Python dependencies
├── run_mcp.sh             # Runner script (handles venv)
└── README.md              # This file
```

## License

MIT
