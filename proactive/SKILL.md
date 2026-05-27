---
name: proactive
description: Create and manage proactive automations that run Claude autonomously on a schedule. Triggers on "proactive", "automation", "create automation", "schedule a task", "monitor my project", "run Claude every X", "add an automation", "list automations", "delete automation".
allowed-tools: Bash(mkdir:*), Read, Write, Edit
---

# Automations

Manage autonomous scheduled Claude runs stored in `~/.punk/proactive.json`. The Punk CLI daemon reads this file and runs each job on its cron schedule.

Do NOT enter plan mode. Execute immediately.

## Core Workflow

1. Read `~/.punk/proactive.json` (or start with `{"jobs":[]}` if missing)
2. Apply the requested change (create / enable / disable / delete)
3. Write the updated JSON back
4. Confirm to the user

## Job Schema

| Field | Type | Notes |
|-------|------|-------|
| id | string | kebab-case, unique e.g. `"ci-watch"` |
| name | string | display name e.g. `"CI Watcher"` |
| cwd | string \| null | absolute project path, or `null` for global |
| schedule | string | 5-field cron expression |
| prompt | string | what Claude should check |
| session | `"new"` \| `"dedicated"` | `dedicated` = same session every run, builds memory over time |
| sessionId | string? | Auto-assigned by CLI on first run — omit on creation |
| allowedTools | string[] | tools Claude may use e.g. `["Bash", "Read", "WebSearch"]` |
| activeHours | object? | `{ start: "09:00", end: "22:00" }` — local machine timezone |
| notify | `"always"` \| `"on-alert"` | `on-alert` = only notify when something needs attention |
| model | string? | `"haiku"`, `"sonnet"`, `"opus"` — omit to use default |
| effort | `"low"` \| `"medium"` \| `"high"` | reasoning effort — omit to use default |
| enabled | boolean | |

## Example Job

```json
{
  "id": "ci-watch",
  "name": "CI Watcher",
  "cwd": "/Users/jack/github/myapp",
  "schedule": "*/15 * * * *",
  "prompt": "Check if CI is passing on the current branch. If it's failing, report which tests are failing and on which branch.",
  "session": "dedicated",

  "allowedTools": ["Bash", "Read"],
  "activeHours": { "start": "09:00", "end": "22:00" },
  "notify": "on-alert",
  "enabled": true
}
```

## Cron Reference

| Schedule | Meaning |
|----------|---------|
| `*/15 * * * *` | Every 15 minutes |
| `0 * * * *` | Every hour |
| `0 9 * * *` | Daily at 9am |
| `0 9 * * 1-5` | Weekdays at 9am |
| `0 8,17 * * *` | At 8am and 5pm daily |

## Commands

**create** — Ask for: name, project (cwd), what to check, how often, which tools needed.
- Defaults: `session: "dedicated"`, `notify: "on-alert"`, `enabled: true`
- Do NOT set `sessionId` — the CLI assigns it automatically on first run
- Keep the prompt focused on what to check — PROACTIVE_OK behavior is handled automatically by the CLI
- Tip: test the prompt manually in a regular Claude thread first to confirm it behaves correctly before scheduling
- Use `model: "haiku"` + `effort: "low"` for simple/frequent checks to reduce cost

**list** — Read and display all jobs from `~/.punk/proactive.json`.

**enable / disable** — Set `enabled: true/false` for the matching id.

**delete** — Remove the job with matching id from the array.

## Important

- `sessionId` is assigned automatically by the CLI on first run — never set or change it manually
- `dedicated` session = Claude remembers context across runs (what it found last time, trends, etc.)
- `PROACTIVE_OK` at start or end of response = job ran fine, no notification sent to phone
- Always use absolute paths for `cwd`

## What to Tell the User
- On create: confirm job name, schedule, and project. Note it starts within 1 minute.
- On list: show id, name, schedule, enabled status, and cwd for each job.
- On delete/toggle: confirm the change was saved.
