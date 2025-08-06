#!/bin/bash

# Script to fetch Google app-specific password using Claude Code
# This script automates the process of:
# 1. Logging into Google account
# 2. Enabling 2-Step Verification if needed
# 3. Generating an app-specific password
# 4. Creating the config.json file

echo "==================================="
echo "Google App Password Fetcher"
echo "==================================="
echo ""
echo "This script will use Claude Code to:"
echo "1. Open a browser and navigate to Google sign-in"
echo "2. Help you log in to your Google account"
echo "3. Generate an app-specific password for Gmail MCP"
echo "4. Create a config.json file with your credentials"
echo ""
echo "Prerequisites:"
echo "- Claude Code must be installed and configured"
echo "- You need your Google account email and password"
echo "- 2-Step Verification (will be enabled if not already active)"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

# Check if claude is installed
if ! command -v claude &> /dev/null; then
    echo "Error: Claude Code is not installed or not in PATH"
    echo "Please install Claude Code first: https://docs.anthropic.com/en/docs/claude-code"
    exit 1
fi

# Get the email address
read -p "Enter your Gmail address: " email

# Create the Claude Code prompt
cat << 'EOF' > /tmp/claude_prompt.txt
Use playwright to:
1. Navigate to https://accounts.google.com/signin
2. Enter the email address and click Next
3. IMPORTANT: Tell the user when the password field is ready and WAIT for them to say they've entered it before proceeding
4. After the user confirms they've entered the password, handle any 2FA verification:
   - Tell the user what verification method is being requested (SMS code, authenticator app, etc.)
   - WAIT for the user to provide the 2FA code or complete the verification
   - Let the user tell you when they've completed the 2FA step
5. After successful login, verify that 2-Step Verification is enabled at https://myaccount.google.com/security
6. If 2-Step Verification is NOT enabled:
   - Inform the user that 2FA is required for app passwords
   - Ask the user if they want to enable it now (yes/no)
   - If YES: Navigate to enable 2FA, handle phone number entry and verification codes as needed
   - If NO: Stop and tell the user they can enable it manually later
7. Once 2-Step Verification IS enabled, navigate to https://myaccount.google.com/apppasswords
8. Create a new app password with the name "Gmail MCP"
9. Extract the generated password exactly as shown
10. Create a config.json file with the email and app password

Important: 
- ALWAYS pause and notify the user when you need them to:
  * Enter their password
  * Complete 2FA verification (SMS code, authenticator app, etc.)
  * Make a decision (like whether to enable 2FA)
  * Provide a phone number for 2FA setup
  * Enter any verification codes
- Wait for explicit confirmation from the user before proceeding after each pause
- If 2FA is not enabled, ask the user before attempting to enable it
- Make sure to capture the 16-character app password exactly as shown
- The config.json should have this format:
{
  "email": "user@gmail.com",
  "app_password": "xxxx xxxx xxxx xxxx"
}
EOF

# Add the email to the prompt
echo "" >> /tmp/claude_prompt.txt
echo "The email address is: $email" >> /tmp/claude_prompt.txt

echo ""
echo "Starting Claude Code..."
echo "Please follow the prompts in Claude Code to complete the process."
echo ""

# Run Claude Code with the prompt
claude < /tmp/claude_prompt.txt

# Clean up
rm -f /tmp/claude_prompt.txt

echo ""
echo "==================================="
echo "Process Complete!"
echo "==================================="
echo ""

# Check if config.json was created
if [ -f "config.json" ]; then
    echo "✓ config.json has been created successfully!"
    echo ""
    echo "You can now run the Gmail IMAP client with:"
    echo "  python3 gmail_imap.py"
    echo "  or"
    echo "  ./run.sh"
else
    echo "⚠ config.json was not created."
    echo "Please check the Claude Code output for any errors."
fi

echo ""
echo "Security Notes:"
echo "- The app password in config.json grants full access to your Gmail"
echo "- Add config.json to .gitignore to prevent accidental commits"
echo "- You can revoke the app password anytime from Google Account settings"
echo ""