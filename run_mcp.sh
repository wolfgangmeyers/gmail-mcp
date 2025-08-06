#!/bin/bash

# Gmail MCP Server runner script
# This ensures the MCP server runs with the correct Python environment

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Check if virtual environment exists
if [ -d "$SCRIPT_DIR/venv" ]; then
    # Activate virtual environment
    source "$SCRIPT_DIR/venv/bin/activate"
elif [ -d "$SCRIPT_DIR/.venv" ]; then
    # Try .venv as alternative
    source "$SCRIPT_DIR/.venv/bin/activate"
fi

# Check if mcp package is installed
if ! python3 -c "import mcp" 2>/dev/null; then
    echo "Installing MCP package..." >&2
    pip install mcp >&2
fi

# Run the MCP server
# Use exec to replace the shell process and preserve stdio handling
exec python3 "$SCRIPT_DIR/server.py"