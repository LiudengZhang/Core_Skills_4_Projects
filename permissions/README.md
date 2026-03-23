# Claude Code Permissions for OSS Contributors

## What This Is

A `settings.local.json` template that gives Claude Code autonomy for local development work while hard-blocking any public-facing GitHub actions.

## Design Principles

1. **Local work is free** — file edits, git operations, test runs, vault updates
2. **GitHub reads are free** — checking PR status, fetching comments, searching issues
3. **GitHub writes are blocked** — posting comments, closing PRs, API mutations
4. **Destructive git is blocked** — `reset --hard`, `clean -f`, `branch -D`

## Why This Split

As an OSS contributor, every GitHub comment is a public artifact under your name. Maintainers and hiring managers read them. Claude should draft replies for your review, never post autonomously.

Meanwhile, mechanical code work (fixing review feedback, rebasing, running tests, updating vault notes) doesn't need human approval — it's local and reversible.

## Setup

1. Copy `settings.local.template.json` to your project's `.claude/settings.local.json`
2. Replace `/path/to/your/oss/workspace/` with your actual workspace path
3. Replace `/path/to/your/obsidian/vault/` with your vault path (or remove if not using one)
4. Add `.claude/settings.local.json` to `.gitignore` (it contains local paths)

## How Deny Rules Work

Deny rules are **hard blocks** — Claude cannot execute these commands even if it tries. They take precedence over allow rules. This is stronger than behavioral instructions in memory, which Claude could theoretically ignore.

## Customization

- Add more `Bash(tool:*)` entries to allow for your specific toolchain (npm, cargo, etc.)
- The `gh api repos/:*` rule allows GET requests (the default). POST/PATCH/DELETE require `-X` or `--method` flags, which are denied.
