# MEMORY — focus_coach_native

Durable decisions and working notes. Newest decisions on top.

## Decisions
- **2026-06-08 — Fork started.** Native rewrite of the FocusMon prototype. Primary
  goal: a shippable native focus monitor that replaces and improves on FocusMon.
- **UI:** Swift (macOS native) is the primary target; Tauri is the fallback if a
  single cross-platform codebase proves preferable to per-platform native.
- **No Ollama in the shipped product.** Ollama allowed only as a dev backend for
  prompt iteration. Shipped app must be a signed/notarized executable for lay users.
- **Must run on Windows too** — do not hard-depend on Apple-only models.
- **Tiered classifier behind a `Backend` interface:**
  1. macOS → Apple Foundation Models (vision).
  2. Windows → bundled small VLM (FastVLM 0.5B) via ONNX Runtime.
  3. Fallback (any OS) → heuristic: frontmost app + window title + YOLO face count.
- **YOLO = cheap pre-pass** (faces → video meeting), not the classifier alone.
- **Privacy:** screenshots classified locally then deleted; nothing leaves the machine.
- **Output contract unchanged:** `running=yes|no|unknown [| focused=yes|no] | note=...`
  so the existing coach pipeline needs no changes.

## Open questions
- Swift native vs. Tauri single-codebase — decide before investing in UI.
- Capture cadence / idle backoff to keep CPU low.
- Where the native runtime hosts the model tier (in-process vs. sidecar).

## Build automation
- An **architect+engineer loop** runs as a Cowork scheduled task: every 2h off-peak
  (21:00–07:59 PT) it does a full build step; light grooming during peak (08:00–21:00).
- It consumes `BACKLOG.md` (small discrete steps), tests each step, and only notifies
  the PM at 🎬 DEMO checkpoints via Slack + Email.
- Canonical loop prompt: `argus/argus_architect/monitor_prompt.md`.
- Demo notifier: `argus/argus_architect/notify.py` (stdlib; reads repo-root `.env`).
- Progress log: `argus/argus_architect/progress.log`.
- The loop **does not touch git** — the existing `*/30` `git_sync.py` cron handles it.

## Status
- Prototype brain (`app/`) is where classification logic gets nailed first, then
  ported to the native target.
- Scaffold not yet built; first off-peak run starts at M0 in BACKLOG.md.
