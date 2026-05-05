---
name: ghost-committer
description: Run the Ghost Committer autonomous tech debt agent on a local git repository. Scans for lint issues, dead code, and vulnerabilities; generates a fix plan via Claude AI; commits changes to a new branch; validates in a sandbox; and opens a GitHub PR with a Slack/Telegram morning digest. Use when asked to: "clean up tech debt", "run overnight code fixes", "scan and patch a repo", "run ghost committer", or "start the autonomous engineer on <repo>". Requires ANTHROPIC_API_KEY, GITHUB_TOKEN, and GITHUB_REPOSITORY in the environment.
---

# Ghost Committer

Autonomous overnight tech debt cleanup agent for Python repositories.

## Pipeline

Runs a 6-layer sequential pipeline:

1. **Scanner** — ruff (lint), vulture (dead code), pip-audit (CVEs)
2. **Planner** — Claude API generates a concrete fix plan from the scan report
3. **Patcher** — GitPython creates a branch, writes fixes, commits
4. **Validator** — Docker sandbox runs `python -m unittest discover` (retries up to 3×)
5. **Delivery** — Opens GitHub PR + sends Slack/Telegram morning digest

## How to invoke

```bash
cd /Users/admin/Downloads/Ghost-Committer
source .venv/bin/activate
python main.py [path/to/repo]
```

Default `path` is `.` (the Ghost Committer repo itself). Pass an absolute path to run on any other repo.

## Environment variables

Required:
- `ANTHROPIC_API_KEY` — Claude API key (planner uses `claude-3-5-sonnet-20240620`)
- `GITHUB_TOKEN` — PAT with `repo` scope (for PR creation)
- `GITHUB_REPOSITORY` — `owner/repo` format

Optional:
- `SLACK_BOT_TOKEN` + `SLACK_CHANNEL` — morning digest to Slack
- `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` — morning digest to Telegram (currently skipped)

Values live in `/Users/admin/Downloads/Ghost-Committer/.env`.

## Fallback behaviour

- No `ANTHROPIC_API_KEY` → planner uses **mock mode** (deterministic plan, no AI cost)
- No `GITHUB_TOKEN` → delivery uses **dry-run mode** (prints PR details, no API call)
- No Docker → validator uses **local fallback** (runs tests directly)
- No Telegram → notification skipped silently

## Cron schedule

Registered in OpenClaw as `ghost-committer-nightly` — runs at 02:00 local time.
Check/edit: `openclaw cron list` → `openclaw cron show ghost-committer-nightly`

## Heartbeat events

The agent emits OpenClaw system events at key pipeline stages so the gateway can track overnight progress. Events are visible via `openclaw system heartbeat last`.
