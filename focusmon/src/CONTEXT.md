# FocusMon — Context

FocusMon is a personal ADHD-focus accountability tool. Every 5 minutes, it checks whether **Fomi** is in an active focus session on the Mac. Twice a day it emails the user and their accountability partners a tone-scaled focus report (win / on_track / struggling), every morning it sends a daily recap against a 6-hour focus goal, and at 11:30am weekdays it sends the user a private "focus coach" email that reads recent patterns in the data and suggests 2–3 evidence-based strategies. A real-time Slack alert fires when Fomi is detected as not actively monitoring during the workday.

---

## Repository layout

```
focusmon/
├── .gitignore
├── logs/                        # One log file per day: YYYY-MM-DD.log
│   └── cron.log                 # stdout/stderr from cron jobs
├── messages/                    # Markdown archive of every generated email
└── src/
    ├── check_fomi.py            # macOS-native detector — is Fomi actively monitoring?
    ├── log_reader.py            # Foundation: parse logs, compute DayStats
    ├── attn_utils.py            # Shared helpers for email scripts (table HTML, plain bar, env)
    ├── attn_4Hourly.py          # Twice-daily partner emails (tone scales with stats)
    ├── attn_daily.py            # 3am daily recap email vs. 6-hour focus goal
    ├── attn_coach.py            # 11:30am weekday private coach email (pattern → strategies)
    ├── sendEmailReport.py       # Self-report CLI (legacy compliance report)
    ├── slack_alert.py           # Slack webhook helper for real-time alerts
    ├── pyproject.toml           # Poetry project metadata
    ├── poetry.lock
    ├── .env                     # Secrets & local config (not committed)
    └── CONTEXT.md               # This file
```

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

### 7. Private focus-coach email — `attn_coach.py`

`attn_coach.py` runs weekdays at 11:30am, half an hour before the midday accountability email, and is sent **only to the user** (`COACH_RECIPIENT` defaults to `SMTP_TO`). It is *not* shared with accountability partners — the coach is private feedback, not accountability.

The script:

1. Loads `DayStats` for the last `COACH_HISTORY_DAYS` days (default `5`) using `log_reader.stats_for_date`.
2. Runs pattern detectors against the history. The detectors and what triggers them:

   | Pattern key | Fires when |
   |---|---|
   | `consistently_low` | Avg compliance < 30% across the window |
   | `cold_start_morning` | 10am–12pm at < 20% AND later in day at least 20pts higher |
   | `afternoon_dip` | 1–4pm at least 15pts lower than both morning and late-day |
   | `late_day_peak` | 5–7pm ≥ 50% AND at least 25pts higher than earlier in day |
   | `improving` | 3+ day window, second half avg > first half avg by 15pts |
   | `chaotic` | Day-to-day variance ≥ 40pts with no other pattern firing |

3. Selects 2–3 strategies from a baked-in catalog (`attn_coach.CATALOG`) whose tags overlap with the detected pattern keys. Each strategy has a name, short description, evidence-grounded detail paragraph, "try today" experiment, and a citation URL.
4. Emails the result and writes a `messages/YYYY-MM-DD-coach.md` archive copy.

The strategies in the catalog are grounded in evidence-based ADHD research — Pomodoro Technique, implementation intentions, body doubling, environmental design, time blocking, the 5-minute rule, circadian-aware "peak window" protection, afternoon-movement, and a "raise the floor" lifestyle reminder for stretches of consistently low compliance. Each carries a source link in the email so the reasoning is auditable.

### 8. Message log — `../messages/`

Every time `attn_4Hourly.py` or `attn_daily.py` runs (including `--dry-run`), it writes a Markdown copy of the email to `messages/` before sending:

- `messages/YYYY-MM-DD-midday.md`
- `messages/YYYY-MM-DD-evening.md`
- `messages/YYYY-MM-DD-daily.md`

The file is `# {subject}` followed by the plain-text body. The directory is created automatically. `write_message_log()` lives in `attn_utils.py`.

### 9. Legacy self-report — `sendEmailReport.py`

The older HTML compliance report. Still works as a CLI for ad-hoc use; not on a schedule anymore.

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
| `COACH_RECIPIENT` | Comma-separated. Falls back to `SMTP_TO`. Recipient(s) of `attn_coach.py` only — partner addresses should NOT be added here. |
| `COACH_HISTORY_DAYS` | How many days of history to consider for pattern detection (default `5`). |

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

# --- private morning focus coach (NOT sent to partners) ---
poetry run python attn_coach.py                               # today, default history window
poetry run python attn_coach.py --dry-run
poetry run python attn_coach.py --days 7                      # consider last 7 days for pattern
poetry run python attn_coach.py --force-pattern late_day_peak --dry-run
poetry run python attn_coach.py --to me@x.com --dry-run

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
- Python ≥ 3.11 (uses `zoneinfo`, PEP 604 unions)

After editing `pyproject.toml`, run `poetry lock && poetry install` from `src/`.

---

## Scheduling

Everything runs from the macOS host crontab. No Claude scheduled tasks involved — the system keeps working whether the Claude desktop app is open or not.

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

# Private morning focus-coach email at 11:30am, weekdays — to user only
30 11 * * 1-5 /bin/bash -lc 'cd ~/PROJ/ASHANBH/personal_agents/focusmon/src && poetry run python attn_coach.py' >> ~/PROJ/ASHANBH/personal_agents/focusmon/logs/cron.log 2>&1
```

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
- **Edit the focus-coach strategy catalog**: append to (or modify) `CATALOG` in `attn_coach.py`. Each `Strategy` has tags that match against detected pattern keys (`consistently_low`, `cold_start_morning`, `afternoon_dip`, `late_day_peak`, `improving`, `chaotic`, plus generic ones like `task_initiation`, `sustained_focus`).
- **Tune coach pattern detection thresholds**: edit `detect_patterns()` in `attn_coach.py` if the auto-fire windows feel too generous or too strict.
- **Adjust how many history days the coach considers**: set `COACH_HISTORY_DAYS` in `.env` (default `5`).
