# BACKLOG — focus_coach_native

The architect/engineer loop consumes this file. Rules:

- Steps are **small, discrete, and independently testable** (≈ one focused sitting each).
- Work top-to-bottom within the active milestone. Check a step off only when its
  **tests pass green**.
- `🎬 DEMO` marks a milestone checkpoint worth notifying the PM about.
- The architect may insert / re-split steps as understanding improves; keep them small.

Status legend: `[ ]` pending · `[~]` in progress · `[x]` done

---

## M0 — Project scaffold & dev harness
- [ ] Create `app/` package skeleton: `app/__init__.py`, `app/config.py` (interval,
      paths, backend choice via env), `app/backends.py` (empty `Backend` ABC),
      `app/focus_service.py` (stub `main()`).
- [ ] Implement the log-line writer matching the contract
      `running=yes|no|unknown [| focused=yes|no] | note=...`; append to a log file.
- [ ] Add `pytest` harness (`tests/`, `pyproject.toml` or `requirements-dev.txt`)
      and a first test asserting the log writer's exact output format.
- [ ] CI-lite: a `make test` / `scripts/test.sh` that runs the suite from a clean checkout.
- 🎬 **DEMO M0:** "Clone → run tests → all green; `python -m app.focus_service` prints a
  well-formed log line." Notify PM with the run command.

## M1 — Heuristic backend, end-to-end
- [ ] `Backend` ABC: `classify(context) -> Decision` where `Decision` carries
      `running`, `focused`, `note`. Document the interface.
- [ ] Cross-platform **frontmost-app + window-title** probe behind a small adapter
      (macOS impl first; Windows/Linux stubbed with TODO). Unit-test the adapter
      with a fake provider.
- [ ] Screen-capture abstraction (e.g. `mss`) that grabs a frame **and deletes it
      immediately** after handing bytes to the backend. Test that no file persists.
- [ ] YOLO face-count **pre-pass interface** (stub returns 0 faces; real weights wired
      later). Test the interface contract, not the model.
- [ ] Heuristic backend: combine frontmost app + title (+ face count) into a
      `Decision`. Table-driven tests for the decision rules.
- [ ] `focus_service` loop: capture → backend → write log line, on an interval from
      config, with clean shutdown. Test one loop iteration with fakes.
- 🎬 **DEMO M1:** "Run the service for 60s; it logs my real focus state from the
  frontmost app + title every N seconds, deleting each capture." Notify PM.

## M2 — Pluggable model backends + graceful fallback
- [ ] Backend registry + platform selection: pick best available
      (Tier1 Apple Foundation Models → Tier2 ONNX FastVLM 0.5B → Tier3 heuristic),
      falling back cleanly when a tier is unavailable. Test the selection logic with
      availability flags mocked.
- [ ] ONNX FastVLM backend skeleton: load weights if present, else raise
      `BackendUnavailable`. Test is skipped when weights absent (no weights in repo).
- [ ] Apple Foundation Models backend skeleton (macOS-gated import). Test that the
      import-guard degrades to fallback off-platform.
- 🎬 **DEMO M2:** "Force each tier via env; show it selecting the right backend and
      falling back to heuristic when none is available." Notify PM.

## M3 — Native shell decision (Swift vs Tauri)
- [ ] Spike: minimal Swift menubar app that shells out to the Python prototype and
      reads the log line. Time-box.
- [ ] Spike: minimal Tauri tray app doing the same.
- [ ] Write `docs/native-shell-decision.md` comparing footprint, packaging,
      cross-platform effort, and pick one. Update CONTEXT.md / MEMORY.md.
- 🎬 **DEMO M3:** "Here's the native shell prototype + the decision writeup." Notify PM.

---

## Notes / follow-ups (architect appends here)
- (none yet)
