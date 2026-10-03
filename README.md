# Agent Session Logger (ASL)

> Record, index, and search AI agent sessions.

## Problem

If you use Claude Code, Codex, or Cursor daily, you've solved problems in previous sessions that you can't find again. Solutions are lost in ephemeral session logs. There's no good way to search across sessions.

## Solution

ASL is a CLI tool that records your agent sessions and makes them searchable.

## Install

```bash
pip install git+https://github.com/yunaremaia/agent-session-logger.git
```

## Quick Start

```bash
# Initialize in your project
asl init

# Record a session
asl record my-feature-session --agent claude-code

# Search across sessions
asl search "auth bug"

# Export a session as markdown
asl export my-feature-session

# List all sessions
asl list
```

## Features

- **Record**: Capture every message in a session (user, assistant, tool calls)
- **Search**: Find solutions across all your past sessions
- **Export**: Generate markdown documentation from any session
- **Lightweight**: SQLite-based, no server required
- **Agent-agnostic**: Works with Claude Code, Codex, Cursor, or any agent

## Storage

Sessions are stored in `.asl/` in your project root:
- `sessions.db` — SQLite database with metadata
- `sessions/` — JSONL files with full message content

## Roadmap

- [ ] Semantic search with embeddings
- [ ] Web dashboard
- [ ] Multi-machine sync
- [ ] Integration with Claude Code/Codex hooks

## License

MIT
