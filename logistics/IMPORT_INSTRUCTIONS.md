# How to Resume Claudia on a New Computer
*Exported: March 17, 2026*

Follow these steps to get Claudia fully operational on a new machine.

---

## Step 1: Install Claude Cowork
Download and install Claude Cowork on the new computer. Sign in with the same Anthropic account.

## Step 2: Connect Gmail
In Claude Cowork, connect the Gmail MCP for shanbhag@gmail.com. This gives Claudia access to read and draft emails.

## Step 3: Connect Claude in Chrome
Install the Claude in Chrome extension on the browser. This lets Claudia send emails (the Gmail MCP can draft but not send — Chrome is needed to hit the Send button).

## Step 4: Load the Memory File
Start a new chat in Claude Cowork and paste the following as your opening message:

---
*Paste this exactly:*

> I'm resuming a planning project. Please read the attached memory file and treat it as your full context going forward. You are Claudia, my AI assistant. Act accordingly.

Then attach or paste the contents of **CLAUDIA_MEMORY.md**.

---

## Step 5: Recreate the Scheduled Tasks

The scheduled tasks live in the Claude app data folder, NOT in your Documents folder, so they don't transfer automatically. You need to recreate them.

Open a chat and say:

> "Create a scheduled task with taskId 'birthday-reply-followup', description 'Monitor replies to the June 13 birthday celebration email and send a researched follow-up to the group', cronExpression '16,46 * * * *', with this prompt:"

Then paste the full prompt from **SCHEDULED_TASKS_EXPORT.md** (Task 1 section).

Then say:

> "Create a one-time scheduled task with taskId 'disable-birthday-followup', description 'Auto-disable the birthday reply follow-up task after 10 days', fireAt '2026-03-26T16:16:00-07:00', with this prompt: Disable the scheduled task with ID 'birthday-reply-followup' by setting enabled to false using the update_scheduled_task tool."

## Step 6: Verify

Ask Claudia: *"What do you know about the birthday planning project?"* — she should be able to summarise the group members, thread status, and private preferences correctly.

---

## Files in This Export Package

| File | Contents |
|---|---|
| `CLAUDIA_MEMORY.md` | Full context: group members, addresses, thread history, private notes, venue strategy |
| `SCHEDULED_TASKS_EXPORT.md` | Both scheduled task configs with full prompts, ready to recreate |
| `IMPORT_INSTRUCTIONS.md` | This file |

---

## Important Notes

- **Cold Turkey timing**: Amit's computer blocks Gmail at certain times. Tasks are set to run at :16 and :46 past the hour (right after Cold Turkey lifts at :15/:45). Keep this cron pattern on the new machine.
- **Gmail account**: Always confirm the sending account is shanbhag@gmail.com before sending.
- **Thread ID**: The active Gmail thread is `19cf592ea6fe99c4`
- **Private notes are in CLAUDIA_MEMORY.md** — Claudia knows what not to say publicly.
