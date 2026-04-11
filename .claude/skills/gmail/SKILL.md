---
name: gmail
description: Send plain-text email via the gmail-mcp OAuth CLI (same tokens as the MCP server). Trigger when email must be sent from scripts, tmux, or Cursor without MCP. Read SKILL.md for the exact path and flags.
---

# Gmail Skill (CLI)

Send mail using **this repository’s** OAuth setup — the same `config.json` and token files as the MCP server. Use this when a worker, cron job, or **Cursor** supervisor cannot call **gmail-mcp** MCP tools directly.

## Prerequisite

- **`config.json`**, **`credentials.json`**, and `python auth.py authorize …` completed. See **README.md** at the repo root.
- Dependencies installed (**venv** recommended).

## Repository layout

Skill lives here: **`.claude/skills/gmail/SKILL.md`**.  
CLI entrypoint (repo root): **`send_email.py`**.

## Canonical script

**`GMAIL_MCP_DIR`** must be the repository root (directory containing `send_email.py`).

```bash
GMAIL_MCP_DIR="${GMAIL_MCP_DIR:-$HOME/code/gmail-mcp}"
PYTHON="${GMAIL_MCP_DIR}/venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="python3"

"$PYTHON" "$GMAIL_MCP_DIR/send_email.py" --help
```

## Usage

**Short body:**

```bash
"$PYTHON" "$GMAIL_MCP_DIR/send_email.py" \
  --to recipient@example.com \
  --subject "Subject line" \
  --body "Plain text body."
```

**Body from a file (UTF-8):**

```bash
"$PYTHON" "$GMAIL_MCP_DIR/send_email.py" \
  --to recipient@example.com \
  --subject "Report" \
  --body-file ./notes.txt
```

**Body from stdin:**

```bash
cat body.txt | "$PYTHON" "$GMAIL_MCP_DIR/send_email.py" \
  --to recipient@example.com \
  --subject "Weekly summary"
```

**Non-default sender** (multi-account `config.json`):

```bash
"$PYTHON" "$GMAIL_MCP_DIR/send_email.py" \
  --account other@gmail.com \
  --to recipient@example.com \
  --subject "Hi" \
  --body "Hello"
```

## Claude Code symlink

Globally available skills expect `~/.claude/skills/<name>` → this folder:

```bash
ln -sfn "$GMAIL_MCP_DIR/.claude/skills/gmail" ~/.claude/skills/gmail
```

## Supervisor / watchdog

When a standing order says to “email the user async” and MCP is unavailable, run `send_email.py` with `--to` set to the user’s address from **`~/.mecha-wolfgang/kb/supervisor-email-recipient.md`** (or persona / explicit user instruction). **Do not** use `wolfgang@gluegroups.com`. Prefer **`--body-file`** for long content to keep secrets out of shell history.

## Scope

This skill covers **CLI send only**. Listing, reading, or searching mail uses **gmail-mcp** MCP tools or future CLI additions in this repo.
