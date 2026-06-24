# FomiForMe — project context

Root-level orientation for the FomiForMe project. Start here. This file is
**shared across versions** and stays at the repo root; it points you to the
active version and explains the layout. (For *how to build/run* a given
version, see that version's `README.md`. For architecture, see `DESIGN.md`;
for current state, `STATUS.md` — both live inside the active version dir.)

## What this is

A native macOS focus monitor replacing fomilab.ai's Fomi: zero-config,
persona-aware (engineer / accountant / doctor), camera + screen perception that
is **classified in memory and never stored**, auto-sent **sanitized**
accountability digests, a coach chat, and a deterrent ladder (warn →
countdown + one-line justification → tomato). See the active version's
`DESIGN.md` for the full spec.

## Layout: shared infra + versioned code

Code is **versioned**; runtime state and monitoring are **shared** across
versions.

```
shanfomi_fable/
  CONTEXT.md            this file — durable root orientation (shared)
  data/                SHARED runtime state: SQLite egress copies, etc.
  logs/                SHARED logs across versions
  argus/               SHARED monitoring layer (ARGUS.md + check_health.py)
  current ->           symlink to the active version dir
  v_YYYYMMDD_HHMMSS/   a code snapshot (one per version)
    app/               Swift package (FomiCore library + FomiForMe executable)
    src/               Python support (fomi4me_db.py, digest_builder.py, launchd/)
    tests/             pytest
    scripts/           build / run / make-app helpers (*.command)
    dist/              built FomiForMe.app (gitignored)
    DESIGN.md          architecture (version-scoped)
    STATUS.md          handoff / current state (version-scoped)
    README.md          usage: how to build & run THIS version
    Makefile  pyproject.toml  .env.example  .gitignore
    data -> ../data    symlink so versioned code reads/writes SHARED data
    logs -> ../logs    symlink so versioned code reads/writes SHARED logs
```

Why this split: `data/`, `logs/`, and `argus/` are not tied to any one
version — they persist and are reused as the code evolves. Each version dir is
a self-contained snapshot of the implementation, but its `data`/`logs` symlinks
point back to the shared root dirs, so digests, the event store, and logs stay
continuous across versions. `argus/check_health.py` finds the active code via
the `current` symlink (falling back to the newest `v_*/`).

## Working with it

- Active code: `cd current` (or the newest `v_*/`).
- Build & run: see `current/README.md`. Quick path:
  `cd current && bash scripts/make_app.command` → produces
  `current/dist/FomiForMe.app`, double-clickable in Finder.
- Monitoring: `python3 argus/src/check_health.py` (run from repo root).
- Start a new version: copy `current/` to a new `v_<newstamp>/`, repoint
  `current`, leave `data/ logs/ argus/` shared.

## Document roles (so nothing's "missing")

- **CONTEXT.md** (root, shared): what the project is + how the repo is laid out.
- **README.md** (per version): how to build and run that version's code.
- **DESIGN.md** (per version): architecture and the milestone plan.
- **STATUS.md** (per version): what's done, what's next, handoff notes.
- **argus/ARGUS.md** (shared): the monitoring/self-healing contract.

## History

- 2026-06-18: M1 builds green on macOS (12 Swift + 14 Python tests). Code
  snapshotted into the first `v_*` dir; `data/ logs/ argus/` kept shared.
