---
name: notes
description: Manage project notes linked to tasks, plans, and components. Notes are stored as JSON files and displayed on the dashboard grouped by plan.
allowed-tools: Read, Write, Bash, Glob, TaskList, TaskGet
---

# Notes Skill

## Purpose
Manage project notes that integrate with the multi-agent workflow. Notes can link to:
- **Tasks** (from TaskList)
- **Plans** (from /dispatch)
- **Dashboard components** (agent work tracking)
- **Figure paths** (specific panels)

## Storage Structure
```
.claude/notes/
├── active/
│   └── note_<timestamp>_<id>.json
└── archived/
    └── note_<timestamp>_<id>.json
```

## Commands

### Add a note
`/note add [options] "content"`

Options:
- `--task <id>` — link to TaskList task
- `--plan <plan_id>` — link to dispatch plan (e.g., `figure_panel_audit`)
- `--component <id>` — link to dashboard component
- `--figure <path>` — link to figure folder (e.g., `03_Final_Panels/01_Figure_1`)
- `--type <type>` — note type: `finding`, `decision`, `blocker`, `question` (default: finding)

Examples:
```
/note add "General observation"
/note add --task 5 "Need to verify sample counts"
/note add --plan figure_panel_audit --type finding "Figure 2 uses wrong column"
/note add --plan figure_panel_audit --type blocker "Need R/NR clarification"
/note add --figure 03_Final_Panels/02_Figure_2 "Panel B needs revision"
```

### Show notes
`/note show [filter]`

Filters:
- `recent` — last 5 notes (default)
- `all` — all active notes
- `--task <id>` — notes for specific task
- `--plan <plan_id>` — notes for specific plan
- `--type <type>` — notes of specific type
- `--component <id>` — notes for specific component

### Archive a note
`/note archive <note_id>`
- Moves the note from `active/` to `archived/`

### List archived
`/note archived`
- Show all archived notes

## Note JSON Schema

```json
{
  "id": "n001",
  "agent": "Executor-Terminal-B",
  "type": "finding",
  "links": {
    "task_id": "3",
    "plan_id": "figure_panel_audit",
    "component_id": "figure_audit",
    "figure_path": "03_Final_Panels/02_Figure_2"
  },
  "content": "The note content here",
  "created": "2026-01-28T10:30:00",
  "tags": ["figure", "revision"]
}
```

### Field Descriptions
| Field | Required | Description |
|-------|----------|-------------|
| `id` | Yes | Unique identifier (n001, n002, ...) |
| `agent` | Yes | Terminal/agent that created the note |
| `type` | Yes | `finding`, `decision`, `blocker`, `question` |
| `links` | No | Object with optional link fields |
| `content` | Yes | The note text |
| `created` | Yes | ISO timestamp |
| `tags` | No | Array of tags for categorization |

### Note Types
| Type | Use When |
|------|----------|
| `finding` | Discovered something during work (default) |
| `decision` | Recording why something was done a certain way |
| `blocker` | Work is blocked, needs resolution |
| `question` | Needs clarification from user/collaborator |

## Workflow

### Adding a Note
1. Parse the command to extract task_id (optional) and content
2. Generate note ID: `n` + 3-digit sequential number
3. Create timestamp
4. Write JSON to `.claude/notes/active/note_<timestamp>_<id>.json`
5. Report: "Note n001 added" (with task link if applicable)

### Showing Notes
1. Glob `.claude/notes/active/*.json`
2. Read and parse each file
3. Filter by task_id if specified
4. Display formatted list

### Archiving
1. Find the note file by ID
2. Move from `active/` to `archived/`
3. Report: "Note n001 archived"

## Python Helper

```python
import json
import os
from datetime import datetime
from pathlib import Path

NOTES_DIR = Path(".claude/notes")
ACTIVE_DIR = NOTES_DIR / "active"
ARCHIVED_DIR = NOTES_DIR / "archived"

def ensure_dirs():
    """Create notes directories if they don't exist."""
    ACTIVE_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVED_DIR.mkdir(parents=True, exist_ok=True)

def get_next_id():
    """Get next sequential note ID."""
    existing = list(ACTIVE_DIR.glob("*.json")) + list(ARCHIVED_DIR.glob("*.json"))
    if not existing:
        return "n001"
    ids = []
    for f in existing:
        try:
            with open(f) as fp:
                data = json.load(fp)
                id_str = data.get("id", "n000")
                if id_str.startswith("n"):
                    ids.append(int(id_str[1:]))
        except:
            continue
    next_num = max(ids, default=0) + 1
    return f"n{next_num:03d}"

def add_note(content, agent="Unknown", note_type="finding",
             task_id=None, plan_id=None, component_id=None, figure_path=None, tags=None):
    """Add a new note with full linking support."""
    ensure_dirs()
    note_id = get_next_id()
    timestamp = datetime.now().isoformat()
    filename = f"note_{timestamp.replace(':', '-').split('.')[0]}_{note_id}.json"

    # Build links object (only include non-None values)
    links = {}
    if task_id: links["task_id"] = task_id
    if plan_id: links["plan_id"] = plan_id
    if component_id: links["component_id"] = component_id
    if figure_path: links["figure_path"] = figure_path

    note = {
        "id": note_id,
        "agent": agent,
        "type": note_type,
        "links": links if links else None,
        "content": content,
        "created": timestamp,
        "tags": tags or []
    }

    filepath = ACTIVE_DIR / filename
    with open(filepath, "w") as f:
        json.dump(note, f, indent=2)

    return note_id, filepath

def get_active_notes(task_id=None, plan_id=None, component_id=None, note_type=None, limit=None):
    """Get active notes with flexible filtering."""
    notes = []
    for f in sorted(ACTIVE_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(f) as fp:
                note = json.load(fp)
                note["_file"] = str(f)

                # Handle both old schema (task_id at root) and new schema (links object)
                links = note.get("links", {}) or {}
                note_task = links.get("task_id") or note.get("task_id")
                note_plan = links.get("plan_id")
                note_comp = links.get("component_id")

                # Apply filters
                if task_id and note_task != task_id:
                    continue
                if plan_id and note_plan != plan_id:
                    continue
                if component_id and note_comp != component_id:
                    continue
                if note_type and note.get("type") != note_type:
                    continue

                notes.append(note)
        except:
            continue
    if limit:
        notes = notes[:limit]
    return notes

def get_notes_by_plan():
    """Group active notes by plan_id for dashboard display."""
    notes = get_active_notes()
    grouped = {"_unlinked": []}

    for note in notes:
        links = note.get("links", {}) or {}
        plan_id = links.get("plan_id")
        if plan_id:
            if plan_id not in grouped:
                grouped[plan_id] = []
            grouped[plan_id].append(note)
        else:
            grouped["_unlinked"].append(note)

    return grouped

def archive_note(note_id):
    """Archive a note by moving it to archived folder."""
    ensure_dirs()
    for f in ACTIVE_DIR.glob("*.json"):
        try:
            with open(f) as fp:
                note = json.load(fp)
                if note.get("id") == note_id:
                    dest = ARCHIVED_DIR / f.name
                    f.rename(dest)
                    return True, dest
        except:
            continue
    return False, None

def get_archived_notes():
    """Get all archived notes."""
    notes = []
    for f in sorted(ARCHIVED_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(f) as fp:
                note = json.load(fp)
                note["_file"] = str(f)
                notes.append(note)
        except:
            continue
    return notes
```

## Output Format

### Default view (recent)
```
📝 Active Notes (5 recent)

[n012] finding | Plan: figure_panel_audit — 2026-02-03 14:30
  🤖 Executor-B
  Figure 2 uses incorrect sample column

[n011] blocker | Plan: figure_panel_audit — 2026-02-03 14:15
  🤖 Executor-B
  Need clarification on R/NR definition for post-treatment

[n010] finding | (unlinked) — 2026-02-02 16:05
  🤖 Commander
  Multi-agent orchestration options documented
```

### Grouped by plan view (/note show --grouped)
```
📝 Active Notes by Plan

📋 figure_panel_audit (3 notes)
  [n012] finding: Figure 2 uses incorrect sample column
  [n011] blocker: Need clarification on R/NR definition
  [n010] question: Should we check external cohort figures?

📋 deg_analysis (1 note)
  [n009] decision: Using Wilcoxon for small sample size

📋 Unlinked (2 notes)
  [n008] finding: CD274-CEACAM correlation validated
  [n007] finding: General observation
```

## Example Usage

```
User: /note add --plan figure_panel_audit --type finding "Figure 2 uses wrong column"
Claude: Note n012 added (finding), linked to plan: figure_panel_audit

User: /note add --plan figure_panel_audit --type blocker "Need R/NR clarification"
Claude: Note n013 added (blocker), linked to plan: figure_panel_audit

User: /note show --plan figure_panel_audit
Claude: [shows notes for that plan]

User: /note show --type blocker
Claude: [shows all blocker notes]

User: /note archive n001
Claude: Note n001 archived
```

## Workflow Integration

### For Executors (during plan execution)
1. When starting a plan, check for existing notes: `/note show --plan <plan_id>`
2. Log findings as you work: `/note add --plan <plan_id> --type finding "..."`
3. If blocked, create blocker note: `/note add --plan <plan_id> --type blocker "..."`
4. Before completing plan, summarize key findings in a note

### For Commander
1. Review blocker notes: `/note show --type blocker`
2. Check executor progress via notes: `/note show --plan <plan_id>`
3. Archive resolved notes: `/note archive <id>`
