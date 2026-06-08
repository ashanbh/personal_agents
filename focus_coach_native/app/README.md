# Focus Coach Native — v0 activity service

Prototype brain. Proves the loop and lets us iterate on classification cheaply.
All processing is local; the screen capture is deleted right after each pass.

```
screencapture → frontmost app + window title (+ optional YOLO)
              → pluggable Backend → activity readout (JSONL) + focusmon log line
              → delete frame
```

## Backends (per-platform, best-available with fallback)

Pick with `--backend`. The shipped app auto-selects; the prototype lets you force one.

| Backend | Tier | Where it ships | Needs |
|---|---|---|---|
| `heuristic` | 3 (fallback) | everywhere | **nothing** — app name + window title + YOLO faces |
| `onnx` | 2 | Windows | bundled small VLM (FastVLM) via ONNX Runtime *(stub)* |
| `apple` | 1 | macOS | Apple Foundation Models, vision (native Swift) *(stub)* |
| `ollama` | dev only | — | local Ollama vision model, for prompt iteration |

`heuristic` is the **default** and runs today with no install. `apple`/`onnx`
are stubs here — they're implemented in the native app; the Python stub documents
the interface and fails loudly if selected.

## Quick start (no model, runs immediately)

```bash
cd ~/PROJ/ASHANBH/personal_agents/focus_coach_native/app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# one capture, print readout + log line, write nothing
python focus_service.py --once --dry-run

# live: capture every 15s, write a focusmon log line at most every 5 min
python focus_service.py
```

First run triggers macOS **Screen Recording** + **Accessibility/Automation**
prompts (the latter for the window title) — approve them.

## Optional: richer dev backend (Ollama vision model)

Only if you want to iterate on the VLM prompt before the native model exists.
Not a shipping target.

```bash
brew install ollama && ollama serve     # separate tab
ollama pull moondream                    # or llava
python focus_service.py --backend ollama --model moondream --once --dry-run
```

## Optional: YOLO object pass

```bash
pip install ultralytics      # heavy (pulls torch)
python focus_service.py --yolo
```

YOLO's job here is narrow: detect faces → "probably a video meeting." It feeds
the backend as a hint; it is not the classifier on its own.

## Outputs

- **Detailed readout:** `../data/activity/<YYYY-MM-DD>.jsonl` — one JSON object
  per capture (category, focused, activity, summary, app, window title, YOLO).
- **focusmon log line:** `~/PROJ/.../focusmon/logs/<YYYY-MM-DD>.log` — same format
  `check_fomi.py` writes, so the existing coach pipeline reads it unchanged.
  Throttled to `--log-interval` (default 5 min).

## Key flags

| Flag | Default | Purpose |
|---|---|---|
| `--backend` | heuristic | heuristic / ollama / apple / onnx |
| `--interval` | 15 | Seconds between captures |
| `--log-interval` | 300 | Min seconds between focusmon log lines |
| `--yolo` / `--no-yolo` | off | YOLO object pass |
| `--model` | moondream | Ollama model (with `--backend ollama`) |
| `--always-classify` | off | Classify even when screen unchanged |
| `--once` / `--dry-run` | off | Single cycle / write nothing |
| `--keep-frames` | off | Debug: keep captures |

## Porting note (Windows)

`capture_frame` (screencapture) and the `osascript` context helpers are macOS.
The Windows port swaps capture for an `mss`/PIL grab and reads the foreground
window via the Win32 API; the `heuristic` and `onnx` backends are otherwise
platform-neutral.
