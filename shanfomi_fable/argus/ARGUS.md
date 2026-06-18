# ARGUS — FomiForMe monitoring contract

Argus is the manager/owner layer for the FomiForMe agent. It wakes
periodically, gathers evidence, and keeps the agent healthy. Loop:
Observe → Diagnose → Plan → Act → Verify → Report (to `argus/logs/`).

## What to observe

1. **App alive** — is the `FomiForMe` process running? (`pgrep -x FomiForMe`)
2. **DB freshness** — newest `events.ts` in the store should be < 10 min old
   during waking hours (the user works most days 9am–7pm Pacific).
3. **Digest sent** — `data/egress/<today>-digest.txt` should exist after 6:05pm;
   `logs/digest.log` should show no traceback.
4. **Permissions health** — a long stretch of `unknown` ticks for browser
   bundles suggests the Automation permission was revoked (BrowserURL failing).
5. **Privacy invariant audit** — no row in `events` may have a `private-*`
   category AND a non-NULL bundle_id/app_name/domain. Zero tolerance.

Run `argus/src/check_health.py` for 1–3 and 5; it exits non-zero with a
machine-readable JSON report on stdout when something is wrong.

## How to act

- App not running → relaunch: `cd app && nohup .build/release/FomiForMe &`
  (or `make run`). Verify a new event row appears within 2 min.
- Digest missing → run `python3 src/digest_builder.py --send`, check log.
- Privacy audit failure → **stop the app immediately**, quarantine the DB file
  (move into `argus/data/quarantine/`), and escalate. This is a sev-1; do not
  attempt silent repair.
- Permission problems → cannot be fixed programmatically; escalate with the
  exact System Settings pane to open.

## Escalation

Notify via the shared notifiers in `~/PROJ/ASHANBH/personal_agents/argus`:
desktop banner for low-sev, email (`notify_via_email.py`) for digest failures,
iMessage (`notify_via_imessage.py`) for sev-1 privacy audit failures.

## Constraints

- Argus never reads identifier columns for `private-*` rows (there should be
  none — that's the audit) and never includes event-level data in
  notifications. Aggregates only, same rule as the digest.
- Fixes must be scoped, reversible, and logged to `argus/logs/health.log`.
- Keep Argus code lighter than core; no new dependencies without reason.
