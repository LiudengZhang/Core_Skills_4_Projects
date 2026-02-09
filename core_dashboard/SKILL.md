---
name: dashboard
description: Generate an HTML dashboard showing current task status, blockers, and next steps. Syncs with TaskList. Use when you need to see project overview or before/after major work sessions.
allowed-tools: Read, Write, Bash, TaskList, TaskGet, Glob, AskUserQuestion
---

# Dashboard Skill

## Purpose
Generate a single-page HTML dashboard in the project folder showing:
- Tasks in progress (with owner/agent)
- Tasks waiting/blocked (with blocker info)
- Tasks needing decisions
- Completed tasks
- **Agent components** (multi-agent work tracking)
- **Recent conversations** (parsed from local JSONL files)
- **Project notes** (from `.claude/notes/`)

## Multi-Agent Architecture

This dashboard supports multiple Claude agents working in separate terminals without overwriting each other's data.

### Folder Structure
```
.claude/dashboard/
├── components/           ← Each agent writes its own JSON file
│   ├── agent_figures.json
│   ├── agent_deg.json
│   └── agent_validation.json
├── shared/               ← Shared cross-agent data (append-only)
│   └── action_items.json
└── config.json           ← Dashboard title, layout order
```

### Component JSON Schema

Each agent component file follows this schema:
```json
{
  "id": "figures",
  "label": "Figure Panels",
  "agent": "Terminal A",
  "updated": "2026-02-02T14:30:00",
  "status": "in_progress",
  "progress": {"done": 3, "total": 8},
  "description": "Working on S07 macrophage origin panels",
  "items": [
    {"name": "Panel A - UMAP", "status": "done"},
    {"name": "Panel B - Boxplot", "status": "in_progress"},
    {"name": "Panel C - Heatmap", "status": "pending"}
  ],
  "blockers": [],
  "recent_outputs": ["04_Final_Panels/S07/panel_a.png"]
}
```

### Agent Identification

Agents **auto-generate** their component ID based on what they're working on:
- Working on figures → component ID: `figures`
- Working on DEG analysis → component ID: `deg_analysis`
- Working on validation → component ID: `validation`

The agent infers this from context (task description, recent files, user instructions).

If unclear, the agent MUST ask: "What should I call this work component?" (e.g., figures, deg, validation)

## Modification Policy

**ADDING content**: Agents may freely add new sections, cards, or information to the dashboard without asking permission.

**REMOVING content**: Before removing any content from the dashboard, the agent MUST:
1. Use `AskUserQuestion` to request permission
2. Explain clearly **what** will be removed and **why** it should be removed
3. Wait for user approval before proceeding

This ensures the dashboard grows and improves while protecting existing information from accidental deletion.

## Commands

### `/dashboard` - Render full dashboard
Reads all components and generates dashboard.html

### `/dashboard update "status message"` - Update agent's component
Agent auto-detects component ID and writes to its own file.

Example: `/dashboard update "3/8 panels done, working on S07 boxplot"`

### `/dashboard register <component_id> "Label"` - Register new component
Creates a new component file with the given ID and label.

Example: `/dashboard register validation "Mechanism Validation"`

## Workflow

### Update Workflow (independent per agent)
```
/dashboard update "3/8 panels done"
    │
    ▼
Agent auto-detects: "I'm working on figures"
    │
    ▼
Writes ONLY to: .claude/dashboard/components/agent_figures.json
(no conflict with other agents)
```

### Render Workflow (any agent)
1. **Get task data**: Call `TaskList` to retrieve all current tasks
2. **Get details**: For each task, optionally call `TaskGet` for full description
3. **Categorize tasks** by status:
   - `in_progress` → In Progress section
   - `pending` with `blockedBy` → Waiting section
   - `pending` without blockedBy → Next Up section
   - `completed` → Done section
4. **Parse components**: Read all JSON files from `.claude/dashboard/components/`
5. **Parse conversations**: Run the conversation parser script to extract recent work
6. **Parse notes**: Read notes from `.claude/notes/active/`
7. **Generate HTML** using the template below
8. **Write to**: `{project_root}/dashboard.html`

## Output Location
Write the dashboard to the current working directory as `dashboard.html`

## Notes Storage
Notes are stored as JSON files in:
- **Active**: `.claude/notes/active/*.json`
- **Archived**: `.claude/notes/archived/*.json`

Use the `/notes` skill to manage notes.

## Component Parser

```python
import json
from pathlib import Path
from datetime import datetime

def parse_components(project_root):
    """Parse all agent components from .claude/dashboard/components/"""
    components_dir = Path(project_root) / ".claude" / "dashboard" / "components"
    components = []

    if components_dir.exists():
        for f in sorted(components_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                with open(f) as fp:
                    comp = json.load(fp)
                    comp["_file"] = f.name
                    components.append(comp)
            except:
                continue

    return components

def update_component(project_root, component_id, label, status, description, progress=None, items=None, blockers=None, recent_outputs=None, agent_name=None):
    """Update or create an agent's component file."""
    components_dir = Path(project_root) / ".claude" / "dashboard" / "components"
    components_dir.mkdir(parents=True, exist_ok=True)

    filename = f"agent_{component_id}.json"
    filepath = components_dir / filename

    # Load existing if present
    existing = {}
    if filepath.exists():
        try:
            with open(filepath) as fp:
                existing = json.load(fp)
        except:
            pass

    # Update fields
    component = {
        "id": component_id,
        "label": label or existing.get("label", component_id.replace("_", " ").title()),
        "agent": agent_name or existing.get("agent", "Unknown"),
        "updated": datetime.now().isoformat(),
        "status": status or existing.get("status", "in_progress"),
        "progress": progress or existing.get("progress"),
        "description": description,
        "items": items or existing.get("items", []),
        "blockers": blockers or existing.get("blockers", []),
        "recent_outputs": recent_outputs or existing.get("recent_outputs", [])
    }

    with open(filepath, "w") as fp:
        json.dump(component, fp, indent=2)

    return filepath

# Usage:
# components = parse_components("/path/to/your/project")
# update_component(project_root, "figures", "Figure Panels", "in_progress", "Working on S07")
```

## Conversation Parser

Run this Python script to extract recent conversations and generate summaries. The script reads JSONL files from `~/.claude/projects/` and creates a brief focus summary for each session.

```python
import json
import os
from datetime import datetime
from pathlib import Path
from collections import Counter
import re

def parse_conversations(project_dir=None, max_sessions=5):
    """Parse recent Claude Code conversations and generate focus summaries."""
    claude_projects = Path.home() / ".claude" / "projects"

    # Find project directories matching current project if specified
    if project_dir:
        project_name = project_dir.replace("/", "-").lstrip("-")
        matching_dirs = [d for d in claude_projects.iterdir()
                        if d.is_dir() and project_name in d.name]
    else:
        matching_dirs = [d for d in claude_projects.iterdir() if d.is_dir()]

    sessions = []

    for proj_dir in matching_dirs:
        jsonl_files = sorted(proj_dir.glob("*.jsonl"),
                            key=lambda f: f.stat().st_mtime, reverse=True)

        for jsonl_file in jsonl_files[:max_sessions]:
            messages = []
            try:
                with open(jsonl_file, "r") as f:
                    for line in f:
                        try:
                            data = json.loads(line)
                            if data.get("type") == "user":
                                content = data.get("message", {}).get("content", "")
                                if isinstance(content, str) and content.strip():
                                    if not content.startswith("<") and len(content) > 10:
                                        messages.append(content)
                        except json.JSONDecodeError:
                            continue
            except Exception:
                continue

            # Skip empty sessions
            if not messages:
                continue

            summary = generate_summary(messages)

            session = {
                "file": jsonl_file.name,
                "modified": datetime.fromtimestamp(jsonl_file.stat().st_mtime),
                "project": proj_dir.name,
                "summary": summary,
                "message_count": len(messages)
            }
            sessions.append(session)

            if len(sessions) >= max_sessions:
                break

    return sessions

def generate_summary(messages):
    """Generate a brief focus summary from user messages."""
    if not messages:
        return "Session started — no activity yet"

    # Combine all messages for analysis
    all_text = " ".join(messages).lower()

    # Topic detection keywords
    topics = {
        "dashboard": ["dashboard", "html", "task tracker", "status page"],
        "figure": ["figure", "panel", "plot", "visualization", "umap", "boxplot"],
        "supplementary": ["supplementary", "supplement", "S0", "additional"],
        "TF analysis": ["tf ", "transcription factor", "regulon", "scenic"],
        "DEG/DGE": ["deg", "dge", "differential", "expression"],
        "cell type": ["cell type", "annotation", "marker", "clustering"],
        "manuscript": ["manuscript", "paper", "writing", "statistics"],
        "skill": ["skill", "claude skill", ".claude/skills"],
        "code/script": ["script", "code", "python", "function"],
        "data": ["data", "h5ad", "anndata", "processing"],
    }

    detected = []
    for topic, keywords in topics.items():
        if any(kw in all_text for kw in keywords):
            detected.append(topic)

    # Build summary based on first message + detected topics
    first_msg = messages[0][:100].strip()

    if detected:
        topic_str = ", ".join(detected[:2])
        # Extract action from first message
        if any(w in first_msg.lower() for w in ["create", "make", "build", "design"]):
            action = "Created/designed"
        elif any(w in first_msg.lower() for w in ["discuss", "plan", "decide"]):
            action = "Discussed/planned"
        elif any(w in first_msg.lower() for w in ["fix", "update", "change", "modify"]):
            action = "Updated/modified"
        elif any(w in first_msg.lower() for w in ["review", "check", "analyze"]):
            action = "Reviewed/analyzed"
        else:
            action = "Worked on"
        return f"{action} {topic_str}"
    else:
        # Fallback: use truncated first message
        return first_msg[:80] + ("..." if len(first_msg) > 80 else "")

# Usage: sessions = parse_conversations("/path/to/your/project")
```

## Notes Parser

```python
import json
from pathlib import Path
from datetime import datetime

def parse_notes(project_root, max_notes=10):
    """Parse active notes from .claude/notes/active/, grouped by plan."""
    notes_dir = Path(project_root) / ".claude" / "notes" / "active"
    archived_dir = Path(project_root) / ".claude" / "notes" / "archived"

    all_notes = []
    archived_count = 0

    # Count archived
    if archived_dir.exists():
        archived_count = len(list(archived_dir.glob("*.json")))

    # Get active notes
    if notes_dir.exists():
        for f in sorted(notes_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
            try:
                with open(f) as fp:
                    note = json.load(fp)
                    note["_file"] = f.name
                    all_notes.append(note)
            except:
                continue

    # Group notes by plan_id
    grouped = {"_unlinked": []}
    for note in all_notes:
        # Handle both old schema (task_id at root) and new schema (links object)
        links = note.get("links", {}) or {}
        plan_id = links.get("plan_id")
        if plan_id:
            if plan_id not in grouped:
                grouped[plan_id] = []
            grouped[plan_id].append(note)
        else:
            grouped["_unlinked"].append(note)

    # Count blockers
    blocker_count = sum(1 for n in all_notes if n.get("type") == "blocker")

    return {
        "all_notes": all_notes[:max_notes],  # For flat display
        "grouped": grouped,                   # For grouped display
        "active_count": len(all_notes),
        "blocker_count": blocker_count,
        "archived_count": archived_count,
        "notes_path": str(notes_dir)
    }

# Usage: notes_data = parse_notes("/path/to/your/project")
```

## HTML Template

Use this exact HTML structure (fill in task data, components, conversations, and notes dynamically):

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Dashboard</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e; color: #eee; padding: 20px; line-height: 1.5;
        }
        .container { max-width: 1000px; margin: 0 auto; }
        header {
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 2px solid #4a4a6a; padding-bottom: 15px; margin-bottom: 25px;
        }
        h1 { font-size: 1.5rem; color: #fff; }
        .timestamp { color: #888; font-size: 0.85rem; }

        /* Two column layout */
        .main-content { display: flex; gap: 25px; }
        .left-column { flex: 1; min-width: 0; }
        .right-column { width: 380px; flex-shrink: 0; }

        .section { margin-bottom: 25px; }
        .section-header {
            display: flex; align-items: center; gap: 10px;
            font-size: 1rem; font-weight: 600; margin-bottom: 12px; color: #ccc;
        }
        .badge {
            background: #4a4a6a; color: #fff; padding: 2px 8px;
            border-radius: 10px; font-size: 0.75rem;
        }
        .task-card {
            background: #252540; border-radius: 8px; padding: 14px 16px;
            margin-bottom: 10px; border-left: 4px solid #666;
        }
        .task-card.in-progress { border-left-color: #f39c12; }
        .task-card.waiting { border-left-color: #e74c3c; }
        .task-card.pending { border-left-color: #3498db; }
        .task-card.completed { border-left-color: #27ae60; opacity: 0.7; }
        .task-id { color: #888; font-size: 0.8rem; margin-right: 8px; }
        .task-title { font-weight: 500; color: #fff; }
        .task-meta { color: #888; font-size: 0.85rem; margin-top: 6px; }
        .task-desc { color: #aaa; font-size: 0.85rem; margin-top: 8px; }
        .blocker { color: #e74c3c; }
        .owner { color: #9b59b6; }
        .empty { color: #666; font-style: italic; padding: 10px 0; }
        .icon { font-size: 1.1rem; }

        /* Component styles */
        .component-card {
            background: #252540; border-radius: 8px; padding: 14px 16px;
            margin-bottom: 10px; border-left: 4px solid #3498db;
        }
        .component-card.in_progress { border-left-color: #f39c12; }
        .component-card.done { border-left-color: #27ae60; }
        .component-card.blocked { border-left-color: #e74c3c; }
        .component-card.pending { border-left-color: #3498db; }
        .component-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 8px;
        }
        .component-label { font-weight: 600; color: #bb86fc; font-size: 0.95rem; }
        .component-progress {
            background: #3a3a5a; color: #fff; padding: 2px 8px;
            border-radius: 10px; font-size: 0.75rem;
        }
        .component-time { color: #666; font-size: 0.75rem; }
        .component-status { color: #ddd; font-size: 0.85rem; margin-bottom: 8px; }
        .component-agent { color: #888; font-size: 0.75rem; margin-bottom: 6px; }
        .component-items {
            list-style: none; padding: 0; margin: 8px 0 0 0;
            font-size: 0.8rem; color: #aaa;
        }
        .component-items li { padding: 2px 0; padding-left: 16px; position: relative; }
        .component-items li::before {
            content: ""; position: absolute; left: 0; top: 8px;
            width: 8px; height: 8px; border-radius: 50%; background: #666;
        }
        .component-items li.done::before { background: #27ae60; }
        .component-items li.in_progress::before { background: #f39c12; }
        .component-items li.pending::before { background: #3498db; }
        .component-outputs {
            margin-top: 8px; padding-top: 8px; border-top: 1px solid #3a3a5a;
            font-size: 0.75rem; color: #666;
        }
        .component-outputs code {
            background: #1a1a2e; padding: 1px 4px; border-radius: 3px;
            font-family: monospace;
        }

        /* Conversation styles */
        .conv-card {
            background: #252540; border-radius: 8px; padding: 12px 14px;
            margin-bottom: 10px; border-left: 4px solid #8e44ad;
        }
        .conv-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 6px;
        }
        .conv-session { font-weight: 600; color: #bb86fc; font-size: 0.9rem; }
        .conv-time { color: #666; font-size: 0.75rem; }
        .conv-summary { color: #ddd; font-size: 0.85rem; line-height: 1.4; }
        .conv-meta { color: #666; font-size: 0.7rem; margin-top: 6px; }

        /* Note styles */
        .note-card {
            background: #252540; border-radius: 8px; padding: 12px 14px;
            margin-bottom: 10px; border-left: 4px solid #16a085;
        }
        .note-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 6px;
        }
        .note-id { font-weight: 600; color: #1abc9c; font-size: 0.9rem; }
        .note-task { color: #3498db; font-size: 0.75rem; }
        .note-time { color: #666; font-size: 0.75rem; }
        .note-content { color: #ddd; font-size: 0.85rem; line-height: 1.4; }
        .note-path {
            color: #555; font-size: 0.7rem; margin-top: 8px;
            font-family: monospace; word-break: break-all;
        }
        .archived-info { color: #666; font-size: 0.75rem; margin-top: 4px; }

        @media (max-width: 800px) {
            .main-content { flex-direction: column; }
            .right-column { width: 100%; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📋 {{DASHBOARD_TITLE}}</h1>
            <span class="timestamp">Updated: {{TIMESTAMP}}</span>
        </header>

        <div class="main-content">
            <div class="left-column">
                <section class="section">
                    <div class="section-header">
                        <span class="icon">⏳</span> In Progress
                        <span class="badge">{{IN_PROGRESS_COUNT}}</span>
                    </div>
                    {{IN_PROGRESS_TASKS}}
                </section>

                <section class="section">
                    <div class="section-header">
                        <span class="icon">🚧</span> Waiting / Blocked
                        <span class="badge">{{WAITING_COUNT}}</span>
                    </div>
                    {{WAITING_TASKS}}
                </section>

                <section class="section">
                    <div class="section-header">
                        <span class="icon">📌</span> Next Up
                        <span class="badge">{{PENDING_COUNT}}</span>
                    </div>
                    {{PENDING_TASKS}}
                </section>

                <section class="section">
                    <div class="section-header">
                        <span class="icon">✅</span> Completed
                        <span class="badge">{{COMPLETED_COUNT}}</span>
                    </div>
                    {{COMPLETED_TASKS}}
                </section>
            </div>

            <div class="right-column">
                <section class="section">
                    <div class="section-header">
                        <span class="icon">🤖</span> Agent Components
                        <span class="badge">{{COMPONENTS_COUNT}}</span>
                    </div>
                    {{COMPONENTS}}
                </section>

                <section class="section">
                    <div class="section-header">
                        <span class="icon">📝</span> Notes
                        <span class="badge">{{NOTES_COUNT}}</span>
                    </div>
                    {{NOTES}}
                    <p class="note-path">📁 {{NOTES_PATH}}</p>
                    {{#if ARCHIVED_COUNT}}<p class="archived-info">📦 {{ARCHIVED_COUNT}} archived</p>{{/if}}
                </section>

                <section class="section">
                    <div class="section-header">
                        <span class="icon">💬</span> Recent Conversations
                        <span class="badge">{{CONV_COUNT}}</span>
                    </div>
                    {{CONVERSATIONS}}
                </section>
            </div>
        </div>
    </div>

</body>
</html>
```

## Task Card Template

For each task, generate a card like this:

```html
<div class="task-card {{STATUS_CLASS}}">
    <span class="task-id">[{{TASK_ID}}]</span>
    <span class="task-title">{{SUBJECT}}</span>
    <div class="task-meta">
        {{#if OWNER}}<span class="owner">👤 {{OWNER}}</span>{{/if}}
        {{#if BLOCKED_BY}}<span class="blocker">⛔ Blocked by: {{BLOCKED_BY}}</span>{{/if}}
    </div>
    {{#if DESCRIPTION}}<div class="task-desc">{{DESCRIPTION}}</div>{{/if}}
</div>
```

## Component Card Template

For each agent component, generate a card:

```html
<div class="component-card {{STATUS}}">
    <div class="component-header">
        <span class="component-label">{{LABEL}}</span>
        {{#if PROGRESS}}<span class="component-progress">{{PROGRESS_DONE}}/{{PROGRESS_TOTAL}}</span>{{/if}}
        <span class="component-time">{{TIME}}</span>
    </div>
    <div class="component-agent">🤖 {{AGENT}}</div>
    <div class="component-status">{{DESCRIPTION}}</div>
    {{#if ITEMS}}
    <ul class="component-items">
        {{#each ITEMS}}
        <li class="{{status}}">{{name}}</li>
        {{/each}}
    </ul>
    {{/if}}
    {{#if RECENT_OUTPUTS}}
    <div class="component-outputs">
        Recent: {{#each RECENT_OUTPUTS}}<code>{{this}}</code> {{/each}}
    </div>
    {{/if}}
</div>
```

## Conversation Card Template

For each session, generate a card with a focus summary:

```html
<div class="conv-card">
    <div class="conv-header">
        <span class="conv-session">Session {{INDEX}}</span>
        <span class="conv-time">{{TIME}}</span>
    </div>
    <div class="conv-summary">{{SUMMARY}}</div>
    <div class="conv-meta">{{MESSAGE_COUNT}} messages</div>
</div>
```

## Note Card Template

For each note, generate a card. The new schema supports `type`, `agent`, and `links` (with plan_id, task_id, component_id, figure_path).

### Flat display (recent notes)
```html
<div class="note-card {{NOTE_TYPE}}">
    <div class="note-header">
        <span class="note-id">[{{NOTE_ID}}]</span>
        <span class="note-type">{{NOTE_TYPE}}</span>
        {{#if PLAN_ID}}<span class="note-plan">📋 {{PLAN_ID}}</span>{{/if}}
        {{#if TASK_ID}}<span class="note-task">Task #{{TASK_ID}}</span>{{/if}}
        <span class="note-time">{{TIME}}</span>
    </div>
    {{#if AGENT}}<div class="note-agent">🤖 {{AGENT}}</div>{{/if}}
    <div class="note-content">{{CONTENT}}</div>
</div>
```

### Grouped by plan display
```html
<div class="note-group">
    <div class="note-group-header">
        <span class="note-group-icon">📋</span>
        <span class="note-group-name">{{PLAN_ID}}</span>
        <span class="note-group-count">({{COUNT}} notes)</span>
    </div>
    <ul class="note-group-items">
        {{#each NOTES}}
        <li class="{{type}}">
            <span class="note-id">[{{id}}]</span>
            <span class="note-type-badge">{{type}}</span>
            {{content}}
        </li>
        {{/each}}
    </ul>
</div>
```

### CSS additions for note types
```css
.note-card.blocker { border-left-color: #e74c3c; }
.note-card.finding { border-left-color: #27ae60; }
.note-card.decision { border-left-color: #3498db; }
.note-card.question { border-left-color: #f39c12; }
.note-type { font-size: 0.7rem; padding: 1px 6px; border-radius: 8px; background: #3a3a5a; }
.note-plan { color: #bb86fc; font-size: 0.75rem; }
.note-agent { color: #888; font-size: 0.7rem; margin-bottom: 4px; }
.note-group { margin-bottom: 12px; }
.note-group-header { color: #bb86fc; font-size: 0.85rem; margin-bottom: 6px; }
.note-group-items { list-style: none; padding-left: 12px; font-size: 0.8rem; }
.note-group-items li { padding: 3px 0; color: #aaa; }
.note-type-badge { font-size: 0.65rem; padding: 1px 4px; border-radius: 4px; margin: 0 4px; }
.note-type-badge.blocker { background: #e74c3c; color: #fff; }
.note-type-badge.finding { background: #27ae60; color: #fff; }
```

## Empty State
If a section has no tasks, show:
```html
<p class="empty">No tasks</p>
```

If no components found:
```html
<p class="empty">No agent components — use /dashboard update to track work</p>
```

If no conversations found:
```html
<p class="empty">No recent conversations</p>
```

If no notes found:
```html
<p class="empty">No notes yet — use /notes add to create one</p>
```

## Example Invocations

### Render dashboard
User says: `/dashboard`
Claude should:
1. Run TaskList
2. Parse the results
3. Parse components from `.claude/dashboard/components/`
4. Run the conversation parser (via Python in Bash)
5. Parse notes from `.claude/notes/active/`
6. Generate the HTML with current data, components, conversations, and notes
7. Write to `dashboard.html`
8. Report: "Dashboard generated: dashboard.html"

### Update component
User says: `/dashboard update "3/8 panels done"`
Claude should:
1. Auto-detect component ID from current work context
2. If unclear, ask user: "What should I call this work component?"
3. Write to `.claude/dashboard/components/agent_{component_id}.json`
4. Report: "Updated component: {component_id}"

### Register new component
User says: `/dashboard register validation "Mechanism Validation"`
Claude should:
1. Create `.claude/dashboard/components/agent_validation.json`
2. Initialize with pending status
3. Report: "Registered component: validation"
