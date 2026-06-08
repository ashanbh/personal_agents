# Focus Coach Native — PRD (Phase A: Prototype)

## Goal

Prove the loop works. One command, run from a terminal, that repeatedly:
**captures the screen → asks a local vision model "is this person working?" →
appends one focusmon-format log line → deletes the image.**

If that loop runs for 30 minutes and produces log lines a human agrees with,
Phase A is done. Everything else (menu bar, settings, auto-start, history) is
deliberately deferred.

## Why a CLI first

The hard, risky part of this project is not the macOS UI — it's whether a tiny
local vision model can reliably tell "working" from "not working" off a
screenshot, fast enough to run every few minutes without being a nuisance. A
CLI strips away every other variable so we can answer that one question. If the
classification is bad, no amount of SwiftUI polish saves the product, and we'd
rather learn that in an afternoon than after building an app.

## Scope (in)

1. **Capture.** Grab the current screen via macOS `screencapture` (CLI) to a
   temp file. Phase A uses the shell tool, not ScreenCaptureKit — fewer moving
   parts, no permission-API code yet. (The OS Screen Recording permission
   prompt still applies; granting it to Terminal is a one-time manual step.)
2. **Downscale.** Resize the capture to a long edge of ~1024px before sending.
   Smaller image = faster inference, lower RAM, and the model doesn't need
   pixel detail to judge gross activity.
3. **Classify.** POST the image to Ollama at `http://localhost:11434/api/generate`
   with model `moondream` and a constrained prompt that asks for a single
   JSON object: `{"state": "working|not_working|unknown", "note": "<short>"}`.
4. **Parse.** Tolerantly extract that JSON (models wrap it in prose). Map to the
   focusmon `running` vocabulary: `working → yes`, `not_working → no`,
   anything unparseable → `unknown`.
5. **Log.** Append exactly one line to `logs/<YYYY-MM-DD>.log` in focusmon's
   format (see below). Local date and timezone.
6. **Delete.** Remove the temp capture immediately after classification —
   before the next loop iteration. The image never persists past one cycle.
7. **Loop.** Sleep `--interval` seconds (default 300, matching focusmon's
   5-minute cadence) and repeat until Ctrl-C.

## Scope (out — explicitly deferred)

- No menu bar, window, icon, or any GUI. (Phase B.)
- No auto-start / login item / launchd. Run it by hand. (Phase B.)
- No settings file or persistence beyond CLI flags. (Phase B.)
- No SQLite / history. (Phase C.)
- No ScreenCaptureKit. `screencapture` shell-out is fine for the prototype.
- No multi-state taxonomy. Phase A is binary `working | not_working` plus
  `unknown` for failures. (`meeting | break | off_task` come in Phase B.)
- No onboarding, no "is Ollama installed?" handholding — if Ollama or the
  model is missing, **error out clearly and exit non-zero.** (Phase C softens
  this.)

## Log line format (must match focusmon exactly)

```
<YYYY-MM-DD HH:MM:SS> <TZ> | running=<yes|no|unknown> | note=<free text>
```

- `running=yes` — model judged the user to be working.
- `running=no` — model judged the user not working.
- `running=unknown` — capture failed, Ollama unreachable, or output unparseable.
- `note` — short model rationale (e.g. `note=code editor, terminal visible`),
  free text, no pipe characters.

This is the same shape `focusmon/src/log_reader.py` parses. The whole point is
that the downstream coach pipeline needs **zero** changes: it already reads
`running=yes|no|unknown` lines and computes `DayStats` from them. Phase A's
output must drop straight into that reader.

**Verification target:** the produced lines parse cleanly through focusmon's
`log_reader.stats_for_date()` with no format errors, and `running=` values
aggregate into compliance the same way Fomi-detected lines do.

## Configuration (CLI flags only)

| Flag | Default | Purpose |
|---|---|---|
| `--interval` | `300` | Seconds between captures. |
| `--ollama-url` | `http://localhost:11434` | Ollama base URL. |
| `--model` | `moondream` | Vision model name. |
| `--log-dir` | `~/PROJ/ASHANBH/personal_agents/focusmon/logs` | Where daily logs go (defaults to focusmon's dir so the coach sees them). |
| `--once` | off | Run a single capture→classify→log cycle and exit (for testing). |
| `--dry-run` | off | Classify and print the line to stdout, but don't write the log or delete nothing of consequence. |
| `--keep-image` | off | Debug only: don't delete the capture, print its path. Off by default — the no-store promise is the default. |

## The classification prompt (first draft)

Sent as the Ollama `prompt`, with the downscaled screenshot as `images[0]`:

> You are looking at a screenshot of someone's computer screen. Decide whether
> the person appears to be doing focused work (coding, writing, reading
> work-related material, in a video meeting, using professional tools) versus
> not working (social media, video streaming, games, shopping, idle desktop).
> Respond with ONLY a JSON object, no other text:
> `{"state": "working" | "not_working" | "unknown", "note": "<5-10 word reason>"}`
> Use "unknown" only if the screen is genuinely ambiguous or unreadable.

We expect to iterate on this wording — prompt quality is itself a Phase A
finding. The note field is what we'll read during manual testing to judge
whether the model is reasoning sensibly or guessing.

## Acceptance criteria (Phase A is "done" when)

1. `app/` contains a runnable SwiftPM CLI target (`swift run`) implementing the
   full loop above.
2. `--once` against a real screen with Ollama up produces a single correct
   focusmon-format log line.
3. Those log lines parse without error through focusmon's `log_reader.py`.
4. With Ollama **down**, the tool prints a clear error naming Ollama and the
   URL, and exits non-zero (no silent `unknown` spam).
5. The temp capture is gone after each cycle (verified: no leftover files in
   `--keep-image`-off mode).
6. **Manual soak test:** leave it running ~30 minutes across a mix of real
   activity (some genuine work, some deliberate goofing off), then eyeball the
   log. The user agrees with the majority of `yes/no` calls. Disagreements are
   noted as prompt/model tuning items, not blockers.

## Risks surfaced in Phase A (record findings, don't necessarily fix)

- **Model accuracy.** Is `moondream` good enough, or do we need LLaVA? Phase A
  produces the first real evidence. Capture concrete misclassifications.
- **Latency.** How long does one capture→classify cycle take on this Mac? If
  it's many seconds, that informs the Phase B interval default and the
  battery conversation.
- **Multi-monitor / multi-space.** `screencapture` defaults — does it grab the
  active display only? Note the behavior; full handling is later.
- **Prompt brittleness.** How often does the model ignore "JSON only"? Drives
  how defensive the parser must be.

## Implementation note

SwiftPM executable target under `app/`. The loop is plain Foundation:
`Process` to shell out to `screencapture` and `sips` (for the resize),
`URLSession` to POST to Ollama, `JSONDecoder` for the response, `FileHandle`
to append the log line. No third-party dependencies. Keep it one file if it
stays small; the goal is a throwaway-quality prototype that answers the
accuracy question, not production code.
