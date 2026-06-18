# Migrating the Birthdays agent (+ Argus) to a new Mac

This sets up the `birthdays` agent and the shared `argus_common/` notification/monitor
layer on a fresh machine. Steps are ordered; the gotchas are called out.

> Throughout, `REPO` = the repo root, e.g. `~/PROJ/ASHANBH/personal_agents`.
> **Do NOT place the repo under `~/Desktop`, `~/Documents`, or `~/Downloads`** —
> macOS TCC blocks launchd from reading scripts in those folders.

## 0. Prerequisites
- macOS with **Messages** signed in to iMessage, and **WhatsApp desktop**
  installed + logged in (only needed if you'll use those channels).
- **Python 3.10+** available to Poetry (the argus_common venv requires ≥3.10).
  The stdlib notifiers also run under the system `python3` (3.9-safe).
- **Homebrew**, **Poetry**, and optionally `brew install terminal-notifier`
  (nicer desktop banners).

## 1. Get the code
```bash
git clone <repo-url> ~/PROJ/ASHANBH/personal_agents
cd ~/PROJ/ASHANBH/personal_agents
```
> `data/`, `logs/`, `.venv/`, and `.env` are **gitignored** — they won't come
> with the clone and must be recreated (below).

## 2. Recreate the secrets file `REPO/.env`
Not in git. Create it with these keys:
```dotenv
SMTP_HOST=...
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_TO=you@example.com
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
IMESSAGE_TO=+1XXXXXXXXXX        # your own number (self-notifications)
WHATSAPP_TO=+1XXXXXXXXXX        # your own number
```

## 3. Build the virtualenvs (per machine — never copy `.venv`)
```bash
cd "$REPO/birthdays" && POETRY_VIRTUALENVS_IN_PROJECT=true poetry install
cd "$REPO/argus_common"     && POETRY_VIRTUALENVS_IN_PROJECT=true poetry install
```
> A `.venv` built on another OS/arch will NOT run here — always rebuild.
> Slack/email require the **argus_common** venv; the wrapper auto-falls back to
> `poetry run` if `argus_common/.venv` is missing/incompatible.

## 4. Seed data
If `birthdays/data/birthdays.csv` didn't come over, the first scheduled run
rebuilds it from the Google Sheet via `sync_birthdays.py`. To seed immediately:
```bash
cd "$REPO/birthdays/src" && python3 sync_birthdays.py
```
(If the sheet ID/GID differs, set `BIRTHDAYS_SHEET_ID` / `BIRTHDAYS_SHEET_GID`.)

## 5. Fix absolute paths (only if username/path differ)
- `birthdays/src/launchd/com.claudia.birthday.plist` hard-codes
  `/Users/amit/PROJ/ASHANBH/personal_agents/...` in `ProgramArguments` and the
  `StandardOutPath`/`StandardErrorPath`. Edit those to the new absolute path.
- `birthday_cron.sh` is **location-independent** (no edit needed).
- The notifier scripts and `sync_birthdays.py` resolve paths relative to
  themselves (no edit needed).

## 6. Install the launchd agent (daily 11:00 local)
```bash
cp "$REPO/birthdays/src/launchd/com.claudia.birthday.plist" ~/Library/LaunchAgents/
launchctl bootout  gui/$(id -u)/com.claudia.birthday 2>/dev/null   # if re-installing
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.claudia.birthday.plist
launchctl print gui/$(id -u)/com.claudia.birthday | grep -E "state|program|path"
```
`state = not running` = loaded and idle (correct).

## 7. Grant macOS permissions (one-time, interactive)
Run the wrapper once so the OS prompts appear, then approve them:
```bash
bash "$REPO/birthdays/src/birthday_cron.sh"
tail -30 "$REPO/birthdays/logs/run.log"
```
Approve under **System Settings → Privacy & Security**:
- **Automation** → allow control of **Messages**, **WhatsApp**, **System Events**.
- **Accessibility** → for the WhatsApp "press Return" keystroke (and notifications).
- **Notifications** → allow banners for `terminal-notifier` (or `Script Editor`).

## 8. Smoke-test each notifier
```bash
cd "$REPO/argus_common"
poetry run python notify_via_slack.py "migration test"
poetry run python notify_via_email.py --subject "migration test" "ok"
python3 notify_via_desktop.py "migration test"
python3 notify_via_imessage.py
python3 notify_via_whatsapp.py
```

## 9. Recreate the Argus monitor (NOT stored in the repo)
The weekly health check is a **Cowork/Claude scheduled task**
(`argus-birthday-monitor`, Wednesdays 3 PM), not a repo file. Recreate it in the
Claude app: a recurring task (cron `0 15 * * 3`) whose prompt points at
`birthdays/argus/ARGUS.md`.

## 10. Verify end-to-end
- Temporarily add a TEST row dated **today** to `birthdays/data/birthdays.csv`
  (e.g. `Amit TEST,,,MM/DD,iMessage,"+1...",`), run `sync`/`preprocess` or just
  the wrapper, and confirm you receive reminders on every channel.
- Remove the TEST row when done.

## Checklist
- [ ] Repo cloned **outside** Desktop/Documents/Downloads
- [ ] `.env` recreated with all 8 keys
- [ ] `birthdays/.venv` and `argus_common/.venv` rebuilt via `poetry install`
- [ ] `birthdays.csv` present (or synced)
- [ ] plist paths updated (if username changed) + launchd loaded
- [ ] Automation + Accessibility + Notifications granted
- [ ] All 5 notifiers tested
- [ ] Argus monitor scheduled task recreated
