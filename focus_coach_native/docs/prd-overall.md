# Focus Coach Native — PRD (overall)

## Problem

People who use Fomi-style focus apps run into the same wall: **you have to
remember to start the session.** ADHD brains are exactly the brains least
likely to do that consistently. Meetings, hyperfocus on a fix, a Slack ping —
all skip the start ritual, all show up later as "0% compliance" days in the
data even though the work happened.

The user already has a working FocusMon + Coach pipeline that turns observed
session data into accountability emails and a tone-scaled morning coach. The
input layer is the weak link: the cron job checks whether *Fomi* is in a
session, not whether *you* are working.

## Audience

Initially: **the author** — ADHD professional, builder, multi-context worker
who wants the coaching pipeline he already has, but with input that doesn't
require remembering anything.

Phase C audience widens to: solo builders, freelancers, and professionals
already buying Hubbub / Fomi but bouncing off the "start a session" friction.

## Value proposition

> A passive coach who notices when you're actually working — and when you're
> not — without you ever pressing Start.

Three commitments that derive from that:

1. **It just runs.** Login item, no rituals.
2. **It's smart.** Uses a small local AI to tell "in a Zoom" from "watching
   YouTube," "writing code" from "reading Reddit," "thinking" from "off-task."
3. **It's yours.** Screenshots are classified and discarded. Nothing leaves
   your Mac.

## Non-goals

- Not a website blocker. Not a Pomodoro timer. Not a task list.
- Not a replacement for Fomi if you like Fomi — it complements it.
- No cloud sync, no team dashboard, no Slack integration. (Maybe later.)

## Principles

(Verbatim from `plan-context.md` — keep these in sight.)

1. **Passive by default.** No "start session" button.
2. **Local AI, no paid API.** Ollama + a small vision model.
3. **Don't store screenshots.** Classify, log, delete.
4. **Feed FocusMon's log format.** No new pipelines downstream.
5. **One thing per screen.**

## Success metrics

Phase-specific success lives in each phase PRD. Globally:

- **Compliance signal quality.** Days where the app is running but the user
  reports they were definitely working that get classified `not working`
  should be < 5%.
- **User intervention rate.** After Phase B, the user should pause / resume /
  open settings < 1× per day on average.
- **Daily coach email quality.** The week after switching from notch
  detection to focus_coach_native as input, the coach email should reference
  observations the user couldn't have inferred from notch data alone.

## Tech direction

- **Native macOS app**, SwiftUI + AppKit, SwiftPM. Sandboxed.
- **Screen capture**: ScreenCaptureKit (macOS 12.3+).
- **AI**: Ollama at `http://localhost:11434`. Default model `moondream`.
  Configurable.
- **Storage**: a small SQLite (history + settings) + the focusmon-format daily
  log file. No screenshots persisted.
- **Schedule**: launchd Login Item once installed. No cron.

## Out-of-scope for this overall PRD

- Per-phase scope, screens, and acceptance criteria — see the phase PRDs.
- Pricing — Phase C only.

## Risks / unknowns to track

- **Vision model quality.** Moondream is tiny; LLaVA is bigger but slower and
  needs more RAM. Need to validate accuracy on a small private benchmark
  before Phase B is "done."
- **Apple permission UX.** ScreenCaptureKit needs Screen Recording permission.
  Onboarding has to handle this gracefully or users will bounce.
- **Battery.** Sustained 5-min screen capture + local inference is not free.
  Phase B should measure and decide whether to pause on battery.
- **What "working" means is contextual.** A staff engineer reading Stack
  Overflow is working; a high-schooler reading the same page is procrastinating.
  We may need user-supplied context per profile. Phase B+.
