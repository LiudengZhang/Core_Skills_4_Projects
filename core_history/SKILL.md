---
name: history
description: Browse and search conversation history from jsonl files. List sessions, summarize conversations, search for keywords across sessions.
allowed-tools: Read, Bash, Glob
---

# History Skill

## Purpose
On-demand browsing and searching of Claude conversation history stored in `~/.claude/projects/` jsonl files.

## Commands

### List sessions
`/history list [n]`
- Shows the most recent n sessions (default: 10)
- Displays: session ID, date, message count, first user message preview

### Summarize a session
`/history summarize <session_id>`
- Parses the session jsonl file
- Returns: date range, message count, key topics, files modified

### Search across sessions
`/history search "keyword"`
- Searches all sessions for the keyword
- Returns: matching sessions with context snippets

### Show session details
`/history show <session_id> [--full]`
- Shows conversation from a specific session
- `--full` shows complete messages, otherwise truncated

## Implementation

### Finding History Files
```python
import os
from pathlib import Path
from glob import glob

# Project-specific history
PROJECT_HISTORY = Path.home() / ".claude/projects/<your-project-slug>"

def get_session_files():
    """Get all session jsonl files sorted by modification time."""
    files = list(PROJECT_HISTORY.glob("*.jsonl"))
    return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)
```

### Parsing JSONL
```python
import json

def parse_session(filepath):
    """Parse a session jsonl file."""
    messages = []
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    msg = json.loads(line)
                    messages.append(msg)
                except json.JSONDecodeError:
                    continue
    return messages

def get_session_summary(filepath):
    """Get summary info for a session."""
    messages = parse_session(filepath)

    user_msgs = [m for m in messages if m.get('type') == 'human']
    assistant_msgs = [m for m in messages if m.get('type') == 'assistant']

    # Get date range
    timestamps = [m.get('timestamp') for m in messages if m.get('timestamp')]

    # Get first user message preview
    first_user = user_msgs[0] if user_msgs else None
    preview = ""
    if first_user:
        content = first_user.get('message', {}).get('content', '')
        if isinstance(content, str):
            preview = content[:100] + "..." if len(content) > 100 else content

    return {
        'session_id': filepath.stem,
        'message_count': len(messages),
        'user_messages': len(user_msgs),
        'assistant_messages': len(assistant_msgs),
        'start_time': min(timestamps) if timestamps else None,
        'end_time': max(timestamps) if timestamps else None,
        'preview': preview
    }
```

### Search Implementation
```python
def search_sessions(keyword, limit=10):
    """Search across all sessions for a keyword."""
    results = []
    keyword_lower = keyword.lower()

    for filepath in get_session_files():
        messages = parse_session(filepath)
        matches = []

        for msg in messages:
            content = msg.get('message', {}).get('content', '')
            if isinstance(content, str) and keyword_lower in content.lower():
                # Extract context around match
                idx = content.lower().find(keyword_lower)
                start = max(0, idx - 50)
                end = min(len(content), idx + len(keyword) + 50)
                snippet = "..." + content[start:end] + "..."
                matches.append({
                    'type': msg.get('type'),
                    'snippet': snippet
                })

        if matches:
            results.append({
                'session_id': filepath.stem,
                'match_count': len(matches),
                'samples': matches[:3]  # First 3 matches
            })

        if len(results) >= limit:
            break

    return results
```

## Output Format

### List Sessions
```
📜 Recent Sessions (10)

1. f035d702-216f-4ab9-b4e3-3211a7110a8d
   Date: 2026-02-03 | Messages: 45
   Preview: "check https://github.com/thedotmack/claude-mem..."

2. abc12345-6789-...
   Date: 2026-02-02 | Messages: 123
   Preview: "Update the dashboard with..."
```

### Search Results
```
🔍 Search: "CEACAM" (5 sessions)

Session: f035d702...
  3 matches
  → "...resistance mechanism involving CEACAM1 expression..."
  → "...CEACAM family members in tumor..."

Session: abc12345...
  1 match
  → "...analyze CEACAM expression levels..."
```

## Example Usage

```
User: /history list 5
Claude: [shows 5 most recent sessions]

User: /history search "figure 4"
Claude: [shows sessions mentioning figure 4]

User: /history summarize f035d702-216f-4ab9-b4e3-3211a7110a8d
Claude: [detailed summary of that session]
```
