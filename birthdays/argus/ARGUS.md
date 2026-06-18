# ARGUS — Birthday Job monitoring contract

Argus is the manager/owner layer for the **birthdays** agent. It wakes
periodically (weekly Cowork scheduled task `argus-birthday-monitor`,
Wednesdays 3 PM), gathers evidence, uses judgment, and **only notifies if
something is genuinely wrong**. A healthy job produces **no** Slack/email —
silence is success. Loop: Observe → Diagnose → Plan → Act → Verify → Report.

## Paths
- Repo root: `/Users/amit/PROJ/ASHANBH/personal_agents`
- Status helper: `birthdays/argus/src/collect_status.py`
- Shared notifiers: `argus_common/notify_via_slack.py`, `argus_common/notify_via_email.py`
- Outcome log: `birthdays/argus/logs/monitor.log`
- Core agent it watches: `birthdays/src/` (daily launchd job `com.claudia.birthday`)

## Observe — gather facts
Run the status helper and read its output (it prints facts only, makes no
decisions, sends nothing):
```
cd /Users/amit/PROJ/ASHANBH/personal_agents
python3 birthdays/argus/src/collect_status.py
```
It reports: presence of the sender / data CSV / wrapper, last run time + age,
FAILED/ERROR/Traceback lines in the last 7 days, the birthday `launchd.err.log`,
and a tail of `birthdays/logs/run.log`.

## Diagnose — what counts as a real problem
- No `run.log`, or no run in the last ~2 days (the job runs daily — it should be fresh).
- Required files missing (sender, data CSV, wrapper).
- **Recent, real** FAILED / ERROR / Traceback lines indicating sends/sync are failing now.
- The Google Sheet **sync failed** (e.g. a line like `ERROR fetching sheet`).
- Non-empty birthday `launchd.err.log`.

Use judgment — don't cry wolf. Ignore failures that are clearly stale leftovers
from earlier debugging if more recent runs succeeded, and ignore the `TEST` rows.
If unsure whether something is a real problem, lean toward a concise heads-up
rather than silence.

## Act / Escalate — notify only if there are issues
Send BOTH Slack and email with a short, specific summary (what's wrong + the key
evidence lines). The notifiers need the shared `argus_common` poetry venv:
```
cd /Users/amit/PROJ/ASHANBH/personal_agents/argus_common
poetry run python notify_via_slack.py "Argus: <summary>"
poetry run python notify_via_email.py --subject "Argus: birthday job issues" "<details>"
```
(If `poetry` isn't available, use `./.venv/bin/python` or `python3` with the
repo `.env` loaded — the notifier scripts read `SMTP_*` and `SLACK_WEBHOOK_URL`
from `/Users/amit/PROJ/ASHANBH/personal_agents/.env`.)

## Report — always log the outcome
Write one line to `birthdays/argus/logs/monitor.log`, e.g.
`2026-06-17 15:00 — healthy, no alert` or
`… — ALERTED: stale run (3.2d), 2 send failures`.

## Constraints
- The birthday job is **remind-only** — Argus never messages birthday recipients,
  and never triggers a `--send`. It only relays health alerts to Amit.
- Fixes must be scoped, reversible, and logged. Keep Argus lighter than core `src/`.
- If healthy: do nothing except write the log line. Do **not** send anything.
