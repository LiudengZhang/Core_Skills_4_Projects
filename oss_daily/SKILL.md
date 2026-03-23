---
name: oss-daily
description: Use once per day (morning) to triage all open PRs, reply to new comments, push fixes, ping stale PRs, and decide whether to start new work.
---

# OSS Daily Run

## Overview

Morning triage of all open PRs. Check, reply, fix, ping, decide. Keep it under 30 minutes most days.

## Step 1: Comprehensive Comment Sweep (5 min)

### 1a. Scan ALL PRs — open AND recently merged/closed

For every PR (open + merged/closed in the last 7 days), check ALL THREE endpoints:
- `gh api repos/OWNER/REPO/issues/NUMBER/comments` — general PR discussion (THIS IS THE MOST COMMONLY MISSED ONE)
- `gh api repos/OWNER/REPO/pulls/NUMBER/comments` — inline code review comments
- `gh api repos/OWNER/REPO/pulls/NUMBER/reviews` — review submissions (approve/request changes)

**Why all three:** GitHub splits PR comments across these endpoints. Issue comments (general discussion) are the most commonly missed — this is where maintainers leave feedback like "please fix tests" or "move Closes X to references". Merged PRs also get final comments (formatting feedback, follow-up suggestions) that deserve acknowledgment.

### 1b. Check linked issues

For each PR that references an issue, also check:
- `gh api repos/OWNER/REPO/issues/ISSUE_NUMBER/comments` — the upstream issue discussion

Maintainers sometimes discuss approach on the issue rather than the PR. If someone commented on the issue after we submitted our PR, we need to know.

### 1c. Verify we actually replied

For every comment found, check whether a reply from us (LiudengZhang) exists AFTER that comment's timestamp. A PR is only "waiting" if our reply exists. No reply = "needs reply", regardless of how long ago the comment was.

### 1d. Filter and categorize

Skip bot comments (codecov, greptile, codex, dependabot, github-actions). Quote the actual comment body, do not summarize or paraphrase.

Categorize each PR into one of:
- **Needs reply** — human comment exists with no reply from us after it
- **Needs fix** — reviewer requested changes we haven't pushed yet
- **Waiting** — we replied or pushed, waiting on reviewer
- **Stale** — no activity for 7+ days after we addressed feedback
- **Merged/Closed (needs reply)** — PR is done but a maintainer left feedback we haven't acknowledged
- **Merged/Closed (done)** — no outstanding comments

## Step 2: Reply and Fix (5-30 min)

For each "needs reply" or "needs fix" PR:

1. Read the full comment thread (not just the new comment)
2. Understand what the reviewer is asking
3. If code changes needed, use `oss-fix` skill to implement
4. Draft reply using `oss-reply` skill
5. Present the reply to user for approval before posting
6. Push code changes, then post the reply

Priority order: warm maintainers first (they respond fast, momentum matters), then others by age.

## Step 3: Ping, Rebase, and Triage Stale PRs (5 min)

### Ping (7+ days silence, feedback addressed)
- Draft a ping using `oss-reply` skill (stale ping template)
- Present to user for approval
- Never ping the same PR more than twice total
- If already pinged twice, mark as deprioritized

**Ping rules (learned the hard way):**
- Wait at least 7 days of true silence before pinging
- Frame as a question, not a demand: "Just checking if anything else is needed" not "Ready to merge?"
- NEVER ping someone who already said they'll do something ("I'll merge this" = wait)
- One ping max. If no response after ping, wait another 2 weeks, then deprioritize
- Silent merge (no comment, just merged) is normal — don't take it personally

### Rebase (weekly, or when conflicts appear)
- For PRs actively under review: rebase onto latest main, force-push
- For PRs waiting 21+ days with zero engagement: consider closing gracefully ("Happy to reopen if this becomes a priority")
- Stale branches with merge conflicts signal abandonment to maintainers

*Evidence: 15 open PRs accumulate staleness. The literature is clear: stale PRs with merge conflicts get abandoned by maintainers.*

## Step 3b: Review One PR in Target Repos (5 min, 2x/week)

Pick 1 open PR in scvi-tools or napari and leave a constructive comment:
- Focus on substance, not style: "Does this handle edge case X?" or "I tested this locally and it works/breaks for me."
- Don't nitpick formatting or imports — that's the maintainer's job.
- Even a "+1 tested locally, works for me" on a reviewed PR adds value.
- This builds credibility faster than submitting PRs. Maintainers notice who engages with the project beyond their own work.

*Evidence: Every online resource names reviewing others' PRs as the #1 credibility builder. We have zero reviewed PRs after 25 submitted. This is the biggest gap.*

## Step 4: Decide on New Work (5 min)

Only start a new PR if ALL of these are true:
- A slot opened (something merged or was closed)
- The target repo has fewer than 3 open PRs from us
- A warm maintainer is available to review (or an issue was explicitly invited)
- User confirms they want to spend time on it today

If starting new work, use `oss-select` and `oss-recon` skills.

## Step 5: Update Vault & Dashboard (2 min)

For any PR that had activity today:
- Update the chain note in `Chains/` (timeline, key quotes, status frontmatter)
- Update the people note if relationship changed (new warmth signal, new quote)
- Update `Dashboard.md` frontmatter if stats changed (merged count, closed count)
- Update `dashboard.html` contribution stages to match GitHub reality
- Every PR must have a chain file — if missing, create one with proper frontmatter

**Chain file frontmatter must include:** `chain`, `status` (active/waiting/merged/closed), `needs_action`, `repos`, `people`, `prs`, `skills`, `layer`, `last_activity`, `submitted`

## Output Format

End the daily run with a short summary:

```
Daily Run — [date]
Replied: #1234 (repo), #5678 (repo)
Fixed: #9012 (repo)
Pinged: #3456 (repo)
New work: none / started #XXXX
Waiting: [count] PRs across [count] repos
```
