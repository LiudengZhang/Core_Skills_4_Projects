#!/usr/bin/env python3
"""
History parsing utilities for Claude conversation archives.
Used by the /history skill.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Project history location
PROJECT_HISTORY = Path.home() / ".claude/projects/<your-project-slug>"


def get_session_files():
    """Get all session jsonl files sorted by modification time (newest first)."""
    if not PROJECT_HISTORY.exists():
        return []
    files = list(PROJECT_HISTORY.glob("*.jsonl"))
    return sorted(files, key=lambda f: f.stat().st_mtime, reverse=True)


def parse_session(filepath):
    """Parse a session jsonl file into a list of messages."""
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

    # Get timestamps
    timestamps = []
    for m in messages:
        ts = m.get('timestamp')
        if ts:
            timestamps.append(ts)

    # Get first user message preview
    preview = ""
    if user_msgs:
        first = user_msgs[0]
        content = first.get('message', {}).get('content', '')
        if isinstance(content, str):
            preview = content[:80].replace('\n', ' ')
            if len(content) > 80:
                preview += "..."

    # Parse dates
    start_date = None
    if timestamps:
        try:
            start_date = datetime.fromisoformat(min(timestamps).replace('Z', '+00:00'))
        except:
            pass

    return {
        'session_id': filepath.stem,
        'filepath': str(filepath),
        'message_count': len(messages),
        'user_messages': len(user_msgs),
        'assistant_messages': len(assistant_msgs),
        'start_date': start_date.strftime('%Y-%m-%d %H:%M') if start_date else 'Unknown',
        'preview': preview
    }


def list_sessions(n=10):
    """List most recent n sessions."""
    files = get_session_files()[:n]
    summaries = []
    for f in files:
        try:
            summaries.append(get_session_summary(f))
        except Exception as e:
            continue
    return summaries


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
                start = max(0, idx - 40)
                end = min(len(content), idx + len(keyword) + 40)
                snippet = content[start:end].replace('\n', ' ')
                if start > 0:
                    snippet = "..." + snippet
                if end < len(content):
                    snippet = snippet + "..."
                matches.append({
                    'type': msg.get('type', 'unknown'),
                    'snippet': snippet
                })

        if matches:
            results.append({
                'session_id': filepath.stem[:12] + "...",
                'full_id': filepath.stem,
                'match_count': len(matches),
                'samples': matches[:3]
            })

        if len(results) >= limit:
            break

    return results


def summarize_session(session_id):
    """Get detailed summary of a specific session."""
    # Find the session file
    for filepath in get_session_files():
        if filepath.stem == session_id or filepath.stem.startswith(session_id):
            messages = parse_session(filepath)
            summary = get_session_summary(filepath)

            # Extract key topics (files mentioned, tools used)
            files_mentioned = set()
            tools_used = defaultdict(int)

            for msg in messages:
                content = msg.get('message', {}).get('content', '')

                # Track tool usage
                if msg.get('type') == 'assistant':
                    tool_use = msg.get('message', {}).get('tool_use', [])
                    if isinstance(tool_use, list):
                        for t in tool_use:
                            if isinstance(t, dict):
                                tools_used[t.get('name', 'unknown')] += 1

            summary['tools_used'] = dict(tools_used)
            return summary

    return None


# CLI interface
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python parse_history.py [list|search|summarize] [args]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == 'list':
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        for i, s in enumerate(list_sessions(n), 1):
            print(f"{i}. {s['session_id'][:20]}...")
            print(f"   Date: {s['start_date']} | Messages: {s['message_count']}")
            print(f"   Preview: {s['preview']}")
            print()

    elif cmd == 'search':
        if len(sys.argv) < 3:
            print("Usage: python parse_history.py search <keyword>")
            sys.exit(1)
        keyword = sys.argv[2]
        results = search_sessions(keyword)
        print(f"Search: \"{keyword}\" ({len(results)} sessions)")
        print()
        for r in results:
            print(f"Session: {r['session_id']}")
            print(f"  {r['match_count']} matches")
            for s in r['samples']:
                print(f"  → {s['snippet']}")
            print()

    elif cmd == 'summarize':
        if len(sys.argv) < 3:
            print("Usage: python parse_history.py summarize <session_id>")
            sys.exit(1)
        session_id = sys.argv[2]
        summary = summarize_session(session_id)
        if summary:
            print(f"Session: {summary['session_id']}")
            print(f"Date: {summary['start_date']}")
            print(f"Messages: {summary['message_count']} ({summary['user_messages']} user, {summary['assistant_messages']} assistant)")
            if summary.get('tools_used'):
                print("Tools used:")
                for tool, count in sorted(summary['tools_used'].items(), key=lambda x: -x[1])[:10]:
                    print(f"  - {tool}: {count}")
        else:
            print(f"Session not found: {session_id}")
