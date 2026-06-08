# Focus Coach Native — Plan & Working Context

A passive, always-on macOS app that watches your screen, uses a local AI to
classify what you're doing, and feeds the existing FocusMon + Coach pipeline.
The gap it closes: **you don't have to remember to turn it on.**

This file is the **living plan**. Update it as we go. Each session: read the
top section, do one chunk, check it off, write a one-line note.

---

## Where this lives

```
~/PROJ/ASHANBH/personal_agents/
├── focusmon/           # existing — cron + logs + accountability emails
├── argus/              # existing — shared notifiers + coach prompt
└── focus_coach_native/       # NEW — the native app
    ├── plan-context.md             # this file
    ├── docs/
    │   ├── prd-overall.md          # global PRD (problem, principles, goals)
    │   ├── prd-A-prototype.md      # Phase A: prove the loop
    │   ├── prd-B-alpha.md          # Phase B: daily-usable for self
    │   └── prd-C-ga.md             # Phase C: releasable
    ├── designs/
    │   ├── A-prototype.html        # mockups (rendered visualize widgets, saved)
    │   ├── B-alpha.html
    │   └── C-ga.html
    └── app/                        # SwiftPM project (added in Phase A)
```

---

## North-star principles (carry through all phases)

1. **Passive by default.** No "start session" button. The app is on whenever
   the Mac is on, paused only on explicit user action or scheduled work hours.
2. **Local AI, no paid API.** Ollama on `localhost:11434`. Default model:
   `moondream` (~1.6 GB, fast, surprisingly good at "is this person working").
3. **Don't store screenshots.** Classify, write a log line, delete the image.
   Show that promise everywhere — it's a feature, not fine print.
4. **Feed FocusMon's log format.** Same `YYYY-MM-DD.log` shape the coach
   already reads. Zero new pipelines downstream.
5. **One thing per screen.** Pattern-match the coach email aesthetic: one
   visual, one insight, one action.

---

## Prior art — what to copy, what to avoid

**Copy:**
- Hubbub's *soft-block* idiom (fade, don't wall off) — for any future "nudge"
  surface.
- Hubbub's *"reads the page, not just the URL"* framing — that's the wedge.
- Fomi's privacy framing: "anonymized locally, never stored." (We go
  further: "never even saved to disk.")

**Avoid:**
- Fomi's "you must start a session" friction. That's the gap we're filling.
- FocusPilot's selfie-camera approach — invasive, hardware-dependent.
- Hubbub's "blocklist" mental model. We classify, not block.

---

## Phase map (high level)

| Phase | Goal | Done when |
|---|---|---|
| **A — Prototype** | Prove the loop works | A CLI that loops: capture → Ollama → log line. Runs from terminal. Output matches focusmon log format. |
| **B — Alpha** | Daily-usable for me | Menu-bar app. Auto-start. Settings, pause, today's count. Replaces my cron-based notch detector. |
| **C — GA** | Releasable to strangers | Onboarding, sparkline history view, code signing, paywall, marketing site. |

Each phase has its own short PRD and design before any code.

---

## Working order — chunks we'll do

Check off as we go. Each chunk should fit in one focused session.

### Setup
- [x] Create folder structure (`docs/`, `designs/`, `app/`).
- [x] Write `plan-context.md`.
- [x] Write `docs/prd-overall.md`.

### Phase A — Prototype
- [x] Write `docs/prd-A-prototype.md`.
- [ ] Sketch `designs/A-prototype.html` (terminal session screenshot mockup).
- [ ] Scaffold SwiftPM CLI under `app/`.
- [ ] Implement: `screencapture` → resize → POST to Ollama → parse JSON →
      append log line.
- [ ] Verify against focusmon's `log_reader.py` shape.
- [ ] Manual test: leave running 30 min, eyeball output.

### Phase B — Alpha
- [ ] Write `docs/prd-B-alpha.md`.
- [ ] Sketch `designs/B-alpha.html` (menu bar + settings window mockups).
- [ ] Refactor app to SwiftUI menu bar + background actor.
- [ ] Settings: interval, work hours, ollama URL/model, pause toggle.
- [ ] Replace focusmon's notch-based 5-min cron with this app.
- [ ] First week of self-dogfood.

### Phase C — GA
- [ ] Write `docs/prd-C-ga.md`.
- [ ] Sketch `designs/C-ga.html` (onboarding, history view, paywall).
- [ ] Onboarding (checks Ollama, pulls model).
- [ ] History sparkline view.
- [ ] Code signing + notarization.
- [ ] Pricing + RevenueCat (or similar).
- [ ] Marketing site.

---

## Open questions (resolve before each phase)

- [ ] **Name.** Working name is `focus_coach_native`. Could pivot to `Glance`,
      `Witness`, `Lookout`, or something else for release.
- [ ] **Default capture interval.** 5 min matches focusmon. Phase A: 5 min.
      Phase B: configurable.
- [ ] **Distinguishing states.** Phase A starts with binary `working | not`.
      Phase B adds `meeting | break | off_task | unknown`. Phase C: settable.
- [ ] **What if Ollama isn't installed?** Phase A: error out clearly. Phase B:
      direct user to install. Phase C: in-app onboarding that checks + offers
      to install.
- [ ] **iCloud sync?** GA-only consideration; default off.

---

## Decisions log (append as we make them)

- **2026-06-09** — Spelling `focus_coach_native` (user-chosen). Sibling of
  `focusmon/`. Default model: `moondream`. Local Ollama only. Log format:
  same as focusmon.
- **2026-06-08** — **Native app platform = Swift, Mac-first.** Chose native
  Swift over Electron (too heavy for an always-on monitor — bundles Chromium)
  and Tauri (cross-platform, kept as the option if we ever want one codebase).
  Rationale: smallest/best-battery, and the heavy integrations (ScreenCaptureKit,
  Core ML, menu bar, launchd, notarization) are all native Mac APIs. Windows is
  a separate later app. Scaffolded `macos/` — a SwiftPM CLI `FocusCapture` that
  captures the main display via `SCScreenshotManager` (macOS 14+) on a timer and
  deletes each frame by default (no-store promise at the capture layer). Built
  on the user's Mac (`swift run`) since ScreenCaptureKit can't compile in the
  Linux sandbox. Next: feed the CGImage to a Core ML classifier instead of
  saving; then wrap in a menu-bar NSApplication.
- **2026-06-08** — **No Ollama in the product; cross-platform brain.** Decided
  the shipped app will NOT depend on Ollama (lay users can't install it) and
  must be able to run on Windows too, so we won't hard-rely on Apple's models.
  Architecture is now **best-available classifier per platform with graceful
  fallback**, behind a pluggable `Backend` interface (`app/backends.py`):
  - Tier 1 macOS: **Apple Foundation Models (vision)** — verified via web that
    the framework now accepts image input (on-device ~300M-param vision
    backbone). Native Swift in the shipped app. No bundle, no download.
  - Tier 2 Windows: **bundled small VLM (Apple's open-source FastVLM, 0.5B)**
    via **ONNX Runtime**. Self-contained, portable weights.
  - Tier 3 anywhere (fallback): **heuristic** — frontmost app name + window
    title + YOLO face count. No model at all; always works.
  - dev only: **Ollama** backend kept purely for prompt iteration; not shipped.
  YOLO is a cheap pre-pass (faces → meeting), NOT the classifier on its own.
  Implemented + unit-tested the Tier-3 heuristic backend today (8/8 cases);
  `--backend` selects the tier; `apple`/`onnx` are documented stubs. Packaging
  target: native Swift app (macOS) signed/notarized; nothing leaves the machine.
- **2026-06-08** — **Architecture pivot.** Moved Phase A off "Swift CLI +
  Ollama only" to a **native-capture → Python analysis service** pipeline:
  `screencapture` → optional YOLO object pass + frontmost-app hint → Ollama
  vision model (mini LM) → **detailed activity readout (JSONL)** *plus* a
  throttled focusmon-format log line (so the existing coach pipeline is
  unchanged). Rationale: the rich readout is the real signal we want to
  improve on; YOLO is a cheap structured pre-pass (faces → meeting), the
  vision-LM is the workhorse. Native Swift capture/menu-bar deferred to
  Phase B; `screencapture` shell-out stands in for now. Built v0 at
  `app/focus_service.py` (+ README, requirements). Verified the emitted log
  line parses through focusmon's `log_reader.py` regex. Privacy unchanged:
  nothing leaves the machine, frames deleted immediately. Models chosen for
  the accuracy test: moondream + llava. Cloud-API path discussed and
  deferred (would break the "nothing leaves the Mac" wedge); kept as a
  possible optional power-user backend later.
- **2026-06-08** — Wrote `docs/prd-A-prototype.md`. Phase A is a throwaway
  SwiftPM CLI proving the capture→Ollama→log loop; uses `screencapture`
  shell-out (not ScreenCaptureKit yet), binary `working|not_working|unknown`,
  writes focusmon-format lines into focusmon's own `logs/` dir so the existing
  coach pipeline needs no changes. Risk to settle in Phase A: is `moondream`
  accurate enough, and what's per-cycle latency. Next chunk: sketch
  `designs/A-prototype.html`.

---

## Reference: prior art links

- Hubbub — https://hubbub.77sparx.com/
- FocusPilot (1-second-everyday) — https://apps.apple.com/us/app/1-second-everyday-focuspilot/id6761648698
- Fomi — https://www.fomilab.ai/
- (Reddit Mac focus app — blocked from fetch; read manually if needed.)

---

## How to use this file

When picking up work:

1. Read **North-star principles** to stay anchored.
2. Find the first unchecked box in **Working order**.
3. Do that one chunk. Don't skip ahead.
4. Check the box. Add a one-line note to **Decisions log** if anything was
   decided.
5. Stop. Next session resumes here.
