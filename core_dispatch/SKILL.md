---
name: dispatch
description: Create and manage task plans for multi-agent execution. Commander/Executor pattern where one terminal creates plans and others execute them.
allowed-tools: Read, Write, Bash, Glob, TaskList, TaskGet
---

# Dispatch Skill

## Purpose
Create and manage task plans that can be executed by separate Claude Code sessions (Executors). Enables a Commander/Executor pattern where one terminal creates plans and other terminals execute them.

## Architecture

```
Commander (Terminal A)          Executor (Terminal B, C, ...)
        │                                │
        │ /dispatch create               │ /dispatch execute <plan>
        │         │                      │         │
        ▼         ▼                      ▼         ▼
   Interview → Save plan ──────────→ Read plan → Execute
                  │                      │
                  ▼                      ▼
        .claude/plans/active/    Update checkboxes
                                         │
                                         ▼
                                 Completion checklist
                                         │
                                         ▼
                                 Update dashboard
                                         │
                                         ▼
                                 Move to completed/
```

## Folder Structure

```
.claude/
├── context/                    ← Project background (executors read first)
│   ├── project.md              ← Main project description
│   ├── style_guide.md          ← Formatting standards
│   └── data_dictionary.md      ← Data documentation
│
├── plans/
│   ├── active/                 ← Plans ready for execution
│   │   └── {plan_name}.md
│   ├── completed/              ← Finished plans (archive)
│   └── templates/              ← Reusable plan templates
│       └── default.md
│
├── dashboard/components/       ← Executor updates status here
└── notes/active/               ← Related notes
```

## Commands

### `/dispatch create "<task description>"`
Commander creates a new plan through structured interview.

**Workflow:**
1. Ask clarifying questions about the task
2. Break into subtasks
3. Identify resources needed
4. Generate completion checklist
5. Save to `.claude/plans/active/{plan_name}.md`
6. Report: "Plan created: {plan_name}.md"

**Example:**
```
User: /dispatch create "Generate S07 macrophage origin figure"
Claude: *asks questions about panels, data, comparisons*
Claude: *generates plan file*
Claude: "Plan created: s07_macrophage_origin.md"
```

### `/dispatch list`
List all plans and their status.

**Output:**
```
Active Plans:
  • s07_macrophage_origin.md (ready, unassigned)
  • deg_tissue_comparison.md (in_progress, Terminal B)

Completed: 3 plans in archive
```

### `/dispatch execute <plan_name>`
Executor picks up and executes a plan.

**Workflow:**
1. Read context files first (`.claude/context/project.md`)
2. Read the plan file
3. Claim the plan (update Assigned field)
4. Check existing notes for this plan: `/note show --plan <plan_name>`
5. Execute subtasks one by one
   - Log findings: `/note add --plan <plan_name> --type finding "..."`
   - If blocked: `/note add --plan <plan_name> --type blocker "..."`
6. Check off items as completed
7. Run completion checklist (ALL must pass)
8. Summarize key findings in a final note
9. Update dashboard component
10. Move plan to `completed/`

**Note-Taking During Execution:**
- Use `--type finding` for discoveries (default)
- Use `--type blocker` when work is blocked (needs resolution)
- Use `--type decision` when making a judgment call
- Use `--type question` when needs clarification from user

**Example:**
```
User: /dispatch execute s07_macrophage_origin
Claude: *reads context*
Claude: *reads plan*
Claude: *checks existing notes for this plan*
Claude: *executes subtasks, logging notes*
Claude: *verifies completion checklist*
Claude: "Plan completed. Dashboard updated. 3 findings logged."
```

### `/dispatch status <plan_name>`
Check status of a specific plan.

### `/dispatch template <template_name>`
Create a plan from a template.

## Plan File Format

```markdown
# Plan: {Title}

## Meta
- ID: plan_{short_name}_{timestamp}
- Created: {ISO datetime}
- Creator: {terminal identifier}
- Status: ready | in_progress | blocked | done
- Assigned: {executor terminal or "unassigned"}

## Context
→ Read first: .claude/context/project.md
→ Style guide: .claude/context/style_guide.md
→ Related notes: {list any relevant notes}

## Goal
{Clear, concise description of what this plan achieves}

## Subtasks
- [ ] 1. {First subtask}
- [ ] 2. {Second subtask}
- [ ] 3. {Third subtask}
...

## Resources
- Data: {paths to input data}
- Output: {paths for output}
- Skills: {relevant skills to use}

## Completion Checklist
Before marking done, verify ALL:

### Output Quality
- [ ] {Quality criterion 1}
- [ ] {Quality criterion 2}

### Statistical Rigor (if applicable)
- [ ] Sample sizes stated
- [ ] Statistical test named
- [ ] P-values reported correctly

### Documentation
- [ ] Output files saved to correct location
- [ ] Code/script preserved

### Dashboard
- [ ] Component status updated to done
- [ ] Output paths recorded in component

## Notes
{Executor adds notes during execution}
```

## Context Files

### project.md (Required)
Main project description that all executors read first.

```markdown
# {Project Name}

## Overview
{What is this project about}

## Key Findings
{Current state of knowledge}

## Data
{What data is available, where it lives}

## Standards
{Statistical requirements, formatting rules}
```

### style_guide.md (Optional)
Formatting and style standards.

### data_dictionary.md (Optional)
Documentation of data files, columns, meanings.

## Completion Checklist Templates

### For Figure Tasks
```markdown
### Output Quality
- [ ] All panels generated at 300 DPI
- [ ] Dimensions match journal specs
- [ ] Font size ≥ 5pt after assembly
- [ ] No truncated labels
- [ ] Color-blind friendly palette

### Statistical Rigor
- [ ] Sample sizes stated (n=X per group)
- [ ] Statistical test named
- [ ] P-values reported (exact values)
- [ ] Multiple testing correction if needed

### Documentation
- [ ] Figure legend drafted
- [ ] Source data exported (CSV)
- [ ] Script saved with comments
```

### For Analysis Tasks
```markdown
### Output Quality
- [ ] Results reproducible
- [ ] Output files properly named
- [ ] No hardcoded paths

### Statistical Rigor
- [ ] Assumptions checked
- [ ] Appropriate test selected
- [ ] Effect sizes reported

### Documentation
- [ ] Methods description written
- [ ] Parameters documented
- [ ] Code commented
```

### For Writing Tasks
```markdown
### Output Quality
- [ ] Follows journal style
- [ ] No placeholder text
- [ ] References formatted

### Accuracy
- [ ] Numbers match source data
- [ ] Figure references correct
- [ ] No contradictions

### Documentation
- [ ] Track changes enabled
- [ ] Version saved
```

## Interview Questions (for /dispatch create)

When creating a plan, ask relevant questions:

**General:**
- What is the end goal?
- What does "done" look like?
- Any deadlines or dependencies?

**For Figures:**
- Which panels are needed?
- What comparisons (R vs NR, tissue types)?
- What statistical tests?
- Output location?

**For Analysis:**
- What data to use?
- What method/pipeline?
- What parameters?
- Where to save results?

**For Writing:**
- Which section?
- What format/journal?
- What content to cover?

## Dashboard Integration

When executor completes a plan:

1. Create/update component in `.claude/dashboard/components/agent_{plan_id}.json`:
```json
{
  "id": "{plan_id}",
  "label": "{plan title}",
  "agent": "{executor terminal}",
  "updated": "{timestamp}",
  "status": "done",
  "progress": {"done": N, "total": N},
  "description": "Completed: {brief summary}",
  "items": [...subtasks with status...],
  "recent_outputs": ["{output paths}"]
}
```

2. The dashboard (`/dashboard`) will automatically show this component.

## Example Session

**Commander (Terminal A):**
```
User: /dispatch create "Generate S07 macrophage origin figure"

Claude: I'll create a plan for this. Let me ask a few questions:

1. Which panels do you need? (e.g., UMAP, boxplot, heatmap)
2. What comparisons? (R vs NR, tissue origin)
3. Which cell subset? (C3_Mac specifically?)
4. Output location?

User: 8 panels total - UMAP, proportion boxplots, marker heatmap, regulon activity.
      Compare R vs NR. Yes C3_Mac. Output to 04_Final_Panels/10_Supplementaries/S07/

Claude: *generates plan*

Plan created: .claude/plans/active/s07_macrophage_origin.md

You can now open a new terminal and run:
  /dispatch execute s07_macrophage_origin
```

**Executor (Terminal B):**
```
User: /dispatch execute s07_macrophage_origin

Claude: Reading context... (project.md)
        Reading plan... (s07_macrophage_origin.md)

        Claiming plan for this terminal.

        Starting execution:

        [1/8] Loading h5ad, subsetting to C3_Mac...
        ✓ Done

        [2/8] Generating Panel A: UMAP by tissue...
        ✓ Done

        ... (continues through all subtasks)

        Running completion checklist:
        ✓ All panels at 300 DPI
        ✓ Dimensions correct
        ✓ Sample sizes stated
        ✓ P-values reported
        ✓ Legend drafted
        ✓ Dashboard updated

        Plan completed. Moved to completed/.
```
