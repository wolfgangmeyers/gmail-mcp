# Gmail MCP Server

A Model Context Protocol (MCP) server that provides Claude with access to Gmail via IMAP.

## Features

- 📧 **List recent emails** - View your inbox messages
- 📖 **Read email contents** - Display full email details
- 🗑️ **Delete emails** - Move emails to trash
- 🔍 **Search emails** - Use IMAP search queries

## Quick Start

### Prerequisites

- Python 3.10 or higher
- A Google account with Gmail
- 2-Factor Authentication enabled on your Google account

### Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/gmail-mcp.git
   cd gmail-mcp
   ```

2. **Create a virtual environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Set up your Gmail credentials** (see below)

4. **Add the server to Claude**:
   ```bash
   # Using the run_mcp.sh wrapper (handles venv automatically)
   claude mcp add gmail-mcp "/path/to/gmail-mcp/run_mcp.sh"
   
   # Or if you manage the venv yourself:
   claude mcp add gmail-mcp "/path/to/venv/bin/python /path/to/gmail-mcp/server.py"
   ```

## Setting Up Gmail Credentials

### Option 1: Automated Setup with Claude Code

If you have Claude Code installed, you can use the automated script to fetch your app-specific password:

1. **Install Playwright MCP server for Claude** (if not already installed):
   ```bash
   claude mcp add playwright npx @playwright/mcp
   ```

2. **Run the automated setup script**:
   ```bash
   ./fetch_app_password.sh
   ```

   This script will:
   - Open a browser and navigate to Google sign-in
   - Guide you through logging in (you'll need to enter your password)
   - Handle 2FA verification during login
   - Enable 2-Step Verification if needed (with your permission)
   - Generate an app-specific password
   - Create the `config.json` file automatically

3. **Follow the prompts** in Claude Code to complete the authentication process

### Option 2: Manual Setup

#### Step 1: Get App-Specific Password

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Click on "2-Step Verification" (must be enabled)
3. Scroll down and click "App passwords"
4. Select "Mail" from the dropdown
5. Click "Generate"
6. Copy the 16-character password (spaces don't matter)

#### Step 2: Create Configuration File

Create a `config.json` file in the same directory as the script:

```json
{
  "email": "your.email@gmail.com",
  "app_password": "your-16-char-app-password"
}
```

**Note:** The spaces in the app password don't matter. You can include or omit them.

## Usage with Claude

Once the server is added to Claude, you can use these commands:

- **List emails**: "Show me my recent emails"
- **Read email**: "Read email with ID 123"
- **Search**: "Search for emails from john@example.com"
- **Delete**: "Delete email ID 456"

### Available Tools

1. **list_emails**
   - Lists recent emails from your inbox
   - Optional parameter: `num_emails` (default: 10)

2. **read_email**
   - Reads a specific email by ID
   - Required parameter: `email_id`

3. **delete_email**
   - Moves an email to trash
   - Required parameter: `email_id`

4. **search_emails**
   - Searches emails using IMAP syntax
   - Required parameter: `query`
   - Optional parameter: `max_results` (default: 20)

### Search Query Examples

- `FROM "sender@example.com"` - Emails from specific sender
- `SUBJECT "meeting"` - Emails with "meeting" in subject
- `UNSEEN` - Unread emails
- `BEFORE 01-Jan-2025` - Emails before a date
- `LARGER 1000000` - Emails larger than 1MB

## Security Notes

- The app password is specific to this application
- Never share or commit your app password
- Add `config.json` to your `.gitignore` file
- You can revoke the app password anytime from Google Account settings

## Troubleshooting

### "Authentication failed"
- Make sure you're using an app-specific password, not your regular Google password
- Verify 2-Factor Authentication is enabled
- Check that the app password was copied correctly

### "IMAP not enabled"
- Gmail IMAP is enabled by default
- If disabled, go to Gmail Settings → Forwarding and POP/IMAP → Enable IMAP

### MCP Server not responding
- Ensure the virtual environment is activated
- Check that the `mcp` package is installed: `pip install mcp`
- Verify `config.json` exists and has valid credentials

## Configuration

### Config File Format

The `config.json` file should contain:

```json
{
  "email": "your.email@gmail.com",
  "app_password": "xxxx xxxx xxxx xxxx"
}
```

- `email`: Your full Gmail address
- `app_password`: The 16-character app-specific password from Google

### Security Best Practices

- Add `config.json` to your `.gitignore` file
- Never commit credentials to version control
- Use environment-specific config files if needed
- Consider using environment variables for production

## Project Structure

```
gmail-mcp/
├── README.md              # This file
├── server.py              # MCP server for Claude
├── config.json            # Your credentials (create this)
├── config.example.json    # Example configuration
├── requirements.txt       # Python dependencies
├── pyproject.toml         # Python package configuration
├── run_mcp.sh            # Runner script (handles venv)
└── fetch_app_password.sh  # Automated setup script
```

## License

MIT