# CONTEXT — focus_coach_native

A passive, always-on **focus monitor**. It periodically captures the screen,
classifies *"is the user working / focused?"*, writes a one-line activity readout,
and **deletes the screenshot immediately**. Nothing leaves the machine.

This is a native rewrite/fork of an earlier prototype (FocusMon). Goal: replace
and improve on that tool with a real shippable app.

## Goals
- **Native, cross-platform** (macOS first, Windows next).
- **Lightweight** — low idle CPU, small memory, no heavyweight runtime deps.
- **Private by default** — captures classified locally, then discarded.
- **Shippable to lay users** — signed/notarized executable, no dev-only deps
  (e.g. no Ollama) in the shipped product.

## Stack (under evaluation)
- **UI / shell:** Swift (macOS native) — primary target. Tauri considered as the
  cross-platform alternative if a single codebase wins over per-platform native.
- **Prototype brain:** Python service (`app/`) to nail classification logic
  cheaply before porting to the native runtime.

## Classifier design — best-available per platform, graceful fallback
Pluggable `Backend` interface so the host picks the strongest option it can run:
1. **Tier 1 — macOS:** Apple Foundation Models (vision, accepts image input).
2. **Tier 2 — Windows:** bundled small VLM (e.g. FastVLM 0.5B) via ONNX Runtime.
3. **Tier 3 — fallback, anywhere:** heuristic — frontmost app + window title +
   YOLO face count (faces → likely video meeting). No model required.

**YOLO** is a cheap pre-pass signal (face/person detection), *not* the sole
classifier. A mini language/vision model is layered on only where it earns its weight.

## Output format
Appends to the existing log contract so the downstream coach needs no changes:
```
running=yes|no|unknown [| focused=yes|no] | note=...
```

## Privacy / repo hygiene
Screen captures (`data/`, `*.png`), model weights (`*.pt`, `*.onnx`, `*.mlmodel`,
`*.mlpackage`) and build output are git-ignored. Captures are never committed.

## Layout (target)
```
focus_coach_native/
├── app/          # Python prototype: focus_service.py + backends.py
├── macos/        # Swift native app (shippable target)
├── docs/         # PRDs, plan/decision log
├── CONTEXT.md    # this file
└── MEMORY.md     # durable decisions / working notes
```
