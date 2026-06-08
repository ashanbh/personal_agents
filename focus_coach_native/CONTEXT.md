# FocusMon — Context

FocusMon is a personal ADHD-focus accountability tool. Every 5 minutes, it checks whether **Fomi** is in an active focus session on the Mac. Twice a day it emails the user and their accountability partners a tone-scaled focus report (win / on_track / struggling), every morning it sends a daily recap against a 6-hour focus goal, and at 11:30am weekdays it sends the user a private "focus coach" email that reads recent patterns in the data and suggests 2–3 evidence-based strategies. A real-time Slack alert fires when Fomi is detected as not actively monitoring during the workday.

All notifications (email + Slack) go through the **shared `argus` helpers** at `~/PROJ/ASHANBH/personal_agents/argus`. FocusMon-specific Argus prompts and helpers live in `~/PROJ/ASHANBH/personal_agents/argus/argus_focusmon/`.

---

## Repository layout

```
~/PROJ/ASHANBH/personal_agents/
├── argus/                                 # Shared notification + monitoring library
│   ├── notify_via_email.py                # send_email(subject, body, to=None, html=None)
│   ├── notify_via_slack.py                # send_slack(text, webhook_url=None)
│   ├── argus_focusmon/                    # FocusMon-specific Argus pieces
│   │   ├── monitor_prompt.md              # Canonical coach prompt (mirrored to fomi-coach-morning)
│   │   └── collect_status.py              # Read-only fact-gathering for the coach
│   └── pyproject.toml
└── focusmon/
    ├── .env                               # Secrets & local config (NOT committed)
    ├── crontab.txt                        # Reference crontab; install with `crontab crontab.txt`
    ├── logs/                              # One log file per day: YYYY-MM-DD.log
    │   └── cron.log                       # stdout/stderr from cron jobs
    ├── messages/                          # Markdown archive of every generated email
    └── src/
        ├── check_fomi.py                  # macOS-native detector — is Fomi actively monitoring?
        ├── log_reader.py                  # Foundation: parse logs, compute DayStats
        ├── attn_utils.py                  # Shared helpers (table HTML, plain bar, env)
        ├── attn_4Hourly.py                # Twice-daily partner emails (tone scales with stats)
        ├── attn_daily.py                  # 3am daily recap email vs. 6-hour focus goal
        ├── sendEmailReport.py             # Self-report CLI; exports send_email() (delegates to argus)
        ├── slack_alert.py                 # FocusMon-side Slack wrapper around argus's notifier
        ├── pyproject.toml                 # Poetry project metadata
        ├── poetry.lock
        └── CONTEXT.md                     # This file
```

Note: the focusmon `.env` lives at the **project root** (`focusmon/.env`), not inside `src/`. `python-dotenv`'s default lookup walks up from cwd to find it when scripts run from `src/`.

---

## How it works

### 1. Every-5-minute check — host crontab

A line in the user's macOS crontab runs every 5 minutes:

```
*/5 * * * * /bin/bash -lc 'cd ~/PROJ/ASHANBH/personal_agents/focusmon/src && poetry run python check_fomi.py --no-slack' >> ~/PROJ/ASHANBH/personal_agents/focusmon/logs/cron.log 2>&1
```

This runs whenever the Mac is awake — independent of whether the Claude desktop app is open. Multiple checks per hour are stored in the log and aggregated into per-hour block bars in the accountability emails.

### 2. `check_fomi.py` — detection

Uses `pyobjc-framework-Quartz` to enumerate windows owned by the Fomi process. The detection signal is **a Fomi-owned window on-screen at Window Server layer ≥ 25** (i.e. above the menu bar, which lives at layer 24). Fomi places a full-screen transparent layer-27 window during active focus sessions and renders the green-dot notch pill inside it. The overlay only exists during an active session, so its presence is the "actively monitoring" signal.

A legacy "small notch-shaped window" check is kept as fallback (`is_notch_indicator`) in case a future Fomi build returns to that pattern.

Outputs:
- Append one line to `logs/<YYYY-MM-DD>.log` (local date).
- If `running=no`, fire a Slack alert via `slack_alert.send_slack()` — prepends `SLACK_MENTION_PREFIX` (e.g. `<!here> <@U03B2APLGG2>`).

### 3. `log_reader.py` — the foundation

Sole owner of the log format. Anything that needs to know "how is Amit doing today?" goes through `stats_for_date(date)`, which returns a `DayStats` with:
- one `HourSlot` per hour in the 10am–7pm work window
- per-slot fields: `checks_yes`, `checks_no`, `checks_unknown`, `check_sequence` (ordered list of `"yes"`/`"no"`/`"unknown"` results within the hour)
- slot statuses: `running | not_running | unknown | missing | lunch | upcoming`
- the hour set as `LUNCH_HOUR` (default `12`) is exempt from compliance if its log entry is missing — it becomes `"lunch"` status instead of `"missing"`
- missing non-lunch hours **penalise** compliance (`missing_n` is included in `total_completed`)
- `compliance_pct = running_n / total_completed`
- helpers `offending_hours` and `focused_hours`

`attn_4Hourly.py`, `attn_daily.py`, and `sendEmailReport.py` all build on this; none parse logs directly.

### 4. `attn_utils.py` — shared email helpers

Holds code used by both accountability email scripts:
- `SUBJECT_NAME` / `ACCOUNTABILITY_RECIPIENTS` — resolved from env
- `block_bar_html(seq)` — renders a row of coloured █ blocks (green=yes, red=no, grey=unknown)
- `all_hours_table_html(slots)` — full 10am–7pm HTML table; multi-check hours show a block bar + %; single-check hours show a plain label
- `plain_bar(slot)` — text/plain equivalent (`[###...] 67%` or `[ok ]` / `[off]` etc.)

### 5. Twice-daily accountability email — `attn_4Hourly.py`

`attn_4Hourly.py` runs at 12pm and 6pm Pacific on weekdays. It picks a **tone** from the day's compliance:

| Compliance | Tone | Framing |
|---|---|---|
| ≥ `ACCOUNTABILITY_WIN_THRESHOLD` (default 90%) | `win` | Celebrate. Lists focused hours. "Drop Amit a high-five." |
| ≥ `ACCOUNTABILITY_THRESHOLD_PCT` (default 70%) | `on_track` | Transparency ping. "No action needed." |
| Below threshold | `struggling` | Lists drifted hours. "A friendly check-in can change the trajectory." |

The same email goes to all of `ACCOUNTABILITY_RECIPIENTS` (user + partners). Every email includes a full hour-by-hour table with sub-hour block bars and an opt-out footer.

### 6. Daily recap email — `attn_daily.py`

`attn_daily.py` runs at 3am (Tue–Sat, covering the previous workday). It compares focused hours against `DAILY_FOCUS_GOAL_HOURS` (default `6`) and sends a brief goal-met / goal-missed summary with the full hour-by-hour table.

### 7. Private focus-coach email — Claude scheduled task `fomi-coach-morning`

Runs weekdays at 11:30am Pacific (with the usual scheduler jitter), half an hour before the midday accountability email. Sent **only to the user** (`COACH_RECIPIENT` falls back to `SMTP_TO`). Not shared with accountability partners — the coach is private feedback, not accountability.

The coach is implemented as a **Claude scheduled task**, not a static Python script. Each run is a fresh Claude session that:

1. Reads the canonical prompt at `argus/argus_focusmon/monitor_prompt.md` (mirrored as the Claude task's SKILL.md).
2. Mounts the project, runs `argus/argus_focusmon/collect_status.py` for facts (file presence, last 5 days of compliance %, hour-by-hour, recent message archives, cron tail).
3. Reads 1–3 recent `messages/*.md` archives to ground itself in what's been communicated.
4. Identifies the dominant pattern *in the actual numbers* (e.g. "Mornings at 8% but afternoons at 55% — your peak window is later than the schedule assumes").
5. Optionally does one focused web search.
6. Picks 2–3 evidence-based strategies from the palette (Pomodoro, If-then plans, Body doubling, Protect peak window, Move at 1pm dip, Five-minute commitment, Strip the workspace, Time-block calendar, Anchor morning routine, Raise the floor, Mark the bright spot) with real source URLs.
7. Sends via `argus.notify_via_email.send_email` from a one-shot Python invocation that loads `focusmon/.env` first so `COACH_RECIPIENT`/`SMTP_TO` resolve correctly.
8. Archives the email to `messages/YYYY-MM-DD-coach.md` and writes one outcome line to `argus/logs/monitor.log`.

The scheduled task fires only while the Claude desktop app is open — if the app is closed at 11:30am that day's coach is skipped. The accountability emails (cron-driven) are unaffected.

**To tune the coach**, edit `argus/argus_focusmon/monitor_prompt.md` and then push the same content into the scheduled task via `mcp__scheduled-tasks__update_scheduled_task` on `fomi-coach-morning`. The .md is the source of truth; the Claude task is a synced copy.

### 8. Message log — `../messages/`

Every time `attn_4Hourly.py` or `attn_daily.py` runs (including `--dry-run`), it writes a Markdown copy of the email to `messages/` before sending:

- `messages/YYYY-MM-DD-midday.md`
- `messages/YYYY-MM-DD-evening.md`
- `messages/YYYY-MM-DD-daily.md`

The file is `# {subject}` followed by the plain-text body. The directory is created automatically. `write_message_log()` lives in `attn_utils.py`.

### 9. Legacy self-report — `sendEmailReport.py`

The older HTML compliance report. Still works as a CLI for ad-hoc use; not on a schedule anymore. Notably, this module also exports the `send_email(to, subject, body, html=False, plain=None)` function that `attn_4Hourly.py`, `attn_daily.py`, and the Claude coach all use. Since the argus migration, the function is a thin wrapper that delegates SMTP to `argus.notify_via_email.send_email` (loaded via `sys.path` from `~/PROJ/ASHANBH/personal_agents/argus`; override with the `ARGUS_DIR` env var).

### 10. Shared notification helpers — `argus/`

All outgoing email and Slack notifications flow through the shared `argus` library at `~/PROJ/ASHANBH/personal_agents/argus`:

- `argus/notify_via_email.send_email(subject, body, to=None, html=None)` — SMTP via `EmailMessage`. When `html` is supplied, the message is multipart/alternative with `body` as the plain-text fallback. Reads SMTP_* from the **personal_agents** repo-root `.env`.
- `argus/notify_via_slack.send_slack(text, webhook_url=None)` — webhook POST via `requests`. Reads `SLACK_WEBHOOK_URL` from the personal_agents `.env`.

FocusMon's `sendEmailReport.send_email` and `slack_alert.send_slack` are thin wrappers that translate the focusmon-side signatures and behaviours (HTML+plain pair, SLACK_MENTION_PREFIX, placeholder-aware skip) into argus calls. If you ever need to send a notification from new code, prefer importing from argus directly:

```python
import sys
sys.path.insert(0, os.path.expanduser("~/PROJ/ASHANBH/personal_agents/argus"))
from notify_via_email import send_email
from notify_via_slack import send_slack
```

FocusMon-specific Argus pieces (prompts, fact-gathering scripts) live in `argus/argus_focusmon/`:

- `monitor_prompt.md` — canonical prompt for the `fomi-coach-morning` Claude task.
- `collect_status.py` — read-only fact-gathering script the coach agent runs.

---

## Environment variables (`.env`)

### Mail
| Variable | Description |
|---|---|
| `SMTP_HOST` | SMTP server (default `smtp.gmail.com`) |
| `SMTP_PORT` | SMTP port (default `587`) |
| `SMTP_USER` | Sender Gmail address. If a comma list, only the first address is used for SMTP auth (Gmail app passwords are tied to a single account). |
| `SMTP_PASSWORD` | Gmail App Password (16-char) |
| `SMTP_TO` | Comma-separated recipient(s) for the legacy self-report. |

### Accountability
| Variable | Description |
|---|---|
| `ACCOUNTABILITY_RECIPIENTS` | Comma-separated. Falls back to `SMTP_TO` if unset. Everyone on this list gets the same email. |
| `ACCOUNTABILITY_THRESHOLD_PCT` | Compliance % at/above which the tone is `on_track` rather than `struggling` (default `70`). |
| `ACCOUNTABILITY_WIN_THRESHOLD` | Compliance % at/above which the tone is `win` (default `90`). |
| `SUBJECT_NAME` | Person the email is *about*, used in subjects and body (default `Amit`). |
| `DAILY_FOCUS_GOAL_HOURS` | Target focused hours for the daily recap (default `6`). |
| `LUNCH_HOUR` | Hour (24h) exempted from compliance if missing from the log (default `12`). |

### Coach (private — not shared with partners)
| Variable | Description |
|---|---|
| `COACH_RECIPIENT` | Comma-separated. Falls back to `SMTP_TO`. Recipient(s) of the `fomi-coach-morning` Claude task — partner addresses should NOT be added here. |

### Argus integration
| Variable | Description |
|---|---|
| `ARGUS_DIR` | Override the path used to import argus's helpers. Defaults to `~/PROJ/ASHANBH/personal_agents/argus`. |

### Detection
| Variable | Description |
|---|---|
| `LOG_DIR` | Path to the `logs/` directory (default `~/PROJ/ASHANBH/personal_agents/focusmon/logs`). |
| `LOCAL_TZ` | IANA timezone for filenames, timestamps, work-window math (default `America/Los_Angeles`). |
| `WORK_START_HOUR`, `WORK_END_HOUR` | Override the 10–19 work window. |
| `FOMI_ACTIVE_LAYER_MIN` | Window Server layer threshold for the active-overlay signal (default `25`). |
| `NOTCH_Y_MAX`, `NOTCH_H_MAX`, `NOTCH_W_MIN`, `NOTCH_W_MAX` | Bounds for the legacy fallback small-notch detector. |

### Slack
| Variable | Description |
|---|---|
| `SLACK_WEBHOOK_URL` | Incoming webhook. `REPLACE_ME` makes `send_slack()` a silent no-op. |
| `SLACK_MENTION_PREFIX` | Prepended to every alert. Use `<!here>` for @here, `<@U…>` for a user mention. |

---

## CLI usage

```bash
# --- twice-daily accountability email ---
poetry run python attn_4Hourly.py                             # send now, infer tone + period
poetry run python attn_4Hourly.py --period midday
poetry run python attn_4Hourly.py --dry-run
poetry run python attn_4Hourly.py --force-tone struggling --dry-run
poetry run python attn_4Hourly.py --to me@x.com --dry-run

# --- daily recap email ---
poetry run python attn_daily.py                               # recap for yesterday
poetry run python attn_daily.py --date 2026-05-28
poetry run python attn_daily.py --dry-run
poetry run python attn_daily.py --to me@x.com --dry-run

# --- detection ---
poetry run python check_fomi.py                               # one-off check
poetry run python check_fomi.py --inspect                     # dump every Fomi window with bounds
poetry run python check_fomi.py --no-log --no-slack           # quiet detection only

# --- legacy self-report ---
poetry run python sendEmailReport.py
poetry run python sendEmailReport.py --date 2026-05-28
poetry run python sendEmailReport.py --dry-run

# --- slack helpers ---
poetry run python slack_alert.py "Manual test message"
poetry run python slack_alert.py --no-mention "Quiet test, no @here ping"
```

---

## Log line format

```
<YYYY-MM-DD HH:MM:SS> <TZ> | running=<yes|no|unknown> | note=<free text>
```

- `running=yes` — Fomi was actively monitoring (notch overlay present)
- `running=no` — Fomi process not running OR running but no active session
- `running=unknown` — check ran but state could not be determined
- A missing hour in the day's log means the Mac was asleep/off, or checks didn't fire during that hour
- `LUNCH_HOUR` (default `12`): a missing entry at this hour is treated as `lunch` (exempt from compliance) rather than `missing`

---

## Dependencies

- `python-dotenv` — loads `.env` into `os.environ`
- `pyobjc-framework-Quartz` (macOS only) — used by `check_fomi.py` to enumerate windows without screenshots
- `requests` — used by `argus/notify_via_slack.py`, which `slack_alert.py` delegates to
- Python ≥ 3.11 (uses `zoneinfo`, PEP 604 unions)

`argus` is **not** pulled in via pip — `sendEmailReport.py` and `slack_alert.py` import it via `sys.path` from `~/PROJ/ASHANBH/personal_agents/argus` (override with `ARGUS_DIR`).

After editing `pyproject.toml` (e.g. when `requests` was added for the argus migration), run `poetry lock && poetry install` from `src/`.

---

## Scheduling

All recurring jobs except the coach run from the macOS host crontab — the system keeps working whether the Claude desktop app is open or not. The morning focus-coach email runs as a Claude scheduled task (see section 7), so it only fires when the Claude app is open at 11:30am.

```
# Fomi state check every 5 minutes, every day
*/5 * * * * /bin/bash -lc 'cd ~/PROJ/ASHANBH/personal_agents/focusmon/src && poetry run python check_fomi.py --no-slack' >> ~/PROJ/ASHANBH/personal_agents/focusmon/logs/cron.log 2>&1

# Midday accountability email, weekdays
0 12 * * 1-5 /bin/bash -lc 'cd ~/PROJ/ASHANBH/personal_agents/focusmon/src && poetry run python attn_4Hourly.py --period midday'  >> ~/PROJ/ASHANBH/personal_agents/focusmon/logs/cron.log 2>&1

# Evening accountability email, weekdays
0 18 * * 1-5 /bin/bash -lc 'cd ~/PROJ/ASHANBH/personal_agents/focusmon/src && poetry run python attn_4Hourly.py --period evening' >> ~/PROJ/ASHANBH/personal_agents/focusmon/logs/cron.log 2>&1

# Daily recap email at 3am (covers previous workday), Tue–Sat
0 3 * * 2-6 /bin/bash -lc 'cd ~/PROJ/ASHANBH/personal_agents/focusmon/src && poetry run python attn_daily.py --yesterday --live' >> ~/PROJ/ASHANBH/personal_agents/focusmon/logs/cron.log 2>&1

# Slack-alert-only check at business hours on weekdays
0 10,11,14,15,16,17 * * 1-5 /bin/bash -lc 'cd ~/PROJ/ASHANBH/personal_agents/focusmon/src && poetry run python check_fomi.py --no-log' >> ~/PROJ/ASHANBH/personal_agents/focusmon/logs/cron.log 2>&1
```

The reference crontab lives at `focusmon/crontab.txt`. Install with `crontab ~/PROJ/ASHANBH/personal_agents/focusmon/crontab.txt`.

The 11:30am **private focus-coach email is a Claude scheduled task** (`fomi-coach-morning`), not a crontab entry — see section 7.

Install with `crontab -e`. Confirm with `crontab -l`.

Sanity checks:
- `sudo launchctl list | grep com.vix.cron` — cron daemon alive
- `tail -f ~/PROJ/ASHANBH/personal_agents/focusmon/logs/cron.log` — watch runs in real time
- `ls /var/mail/$USER` — cron emails errors here by default

On modern macOS, `/usr/sbin/cron` may need Full Disk Access (System Settings → Privacy & Security → Full Disk Access) to write files. If `cron.log` stays empty after a fire, that's the first thing to check.

---

## Tuning the system

- **Change work window**: set `WORK_START_HOUR` / `WORK_END_HOUR` in `.env`.
- **Change tone cutoffs**: `ACCOUNTABILITY_THRESHOLD_PCT` and `ACCOUNTABILITY_WIN_THRESHOLD` in `.env`.
- **Add/remove accountability partners**: edit `ACCOUNTABILITY_RECIPIENTS` in `.env`. No code change.
- **Stop accountability emails temporarily**: comment out the relevant crontab lines.
- **Adjust detection if Fomi changes its overlay layer**: set `FOMI_ACTIVE_LAYER_MIN` in `.env`, or run `check_fomi.py --inspect` while a session is active to see current layer values.
- **Soften / sharpen email wording**: edit the three tone branches in `build_email()` in `attn_4Hourly.py`.
- **Change daily focus goal**: set `DAILY_FOCUS_GOAL_HOURS` in `.env`.
- **Change lunch exemption hour**: set `LUNCH_HOUR` in `.env`.
- **Tune the focus-coach voice, strategy palette, or constraints**: edit `argus/argus_focusmon/monitor_prompt.md` then sync the same content into the `fomi-coach-morning` Claude scheduled task via `mcp__scheduled-tasks__update_scheduled_task`.
- **Disable the focus coach**: disable `fomi-coach-morning` from the Claude sidebar.
- **Point focusmon at a different argus install**: set `ARGUS_DIR` in `.env` (defaults to `~/PROJ/ASHANBH/personal_agents/argus`).
- **Add a brand-new notification surface** (Discord, SMS, etc.): add it to `argus/` as a sibling of `notify_via_email.py` / `notify_via_slack.py`; consumers across all personal-agents projects pick it up automatically.
- **Adjust how many history days the coach considers**: set `COACH_HISTORY_DAYS` in `.env` (default `5`).
