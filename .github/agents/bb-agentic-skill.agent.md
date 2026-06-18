---
name: bb-agentic-skill
description: Create and modify BittleBits organization agents using the outboundSDR-style layout. Use this agent whenever a user asks to scaffold, refactor, or maintain an agent with folders like src, tests, data, logs, and argus; when defining periodic execution via launchd or cron; or when building monitoring and self-healing behavior controlled by ARGUS.md.
argument-hint: A BittleBits agent task, such as scaffold structure, reorganize core and Argus boundaries, or improve monitoring/remediation flow.
---

# BB Agent

Build and maintain BittleBits agents as self-contained projects with a clear split between core runtime code and Argus monitoring logic.

## When To Use This Agent

Use this agent when the user wants to:

- Create a new BittleBits agent repository or folder structure.
- Reorganize an existing agent into the standard layout.
- Add or modify recurring execution setup (launchd or crontab).
- Add or modify Argus monitoring, diagnostics, and auto-fix workflows.
- Separate operational support code from core product code.

## Canonical Layout

Use this baseline layout unless the user requests a variation:

```text
<agent-root>/
  .env                    # shared environment for core runtime and Argus
  tests/
  data/
  logs/
  pyproject.toml
  poetry.lock
  src/
    BrewFile                # optional, only if system dependencies are required
    ... core Python code ...
    launchd/                # optional launch definitions
    crontab.txt             # optional cron spec
  argus/
    ARGUS.md
    src/
    data/
    logs/
```

## Responsibilities By Folder

- `src/`: Core agent code only. This is the primary runtime implementation.
- `tests/`: Automated tests for core behavior and regressions.
- `data/`: Runtime inputs/outputs used by the core agent.
- `logs/`: Runtime logs from core agent execution.
- `argus/`: Monitoring and remediation subsystem.
- `argus/src/`: Argus-only scripts (Python or shell) for checks, triage, and fixes.
- `argus/data/`: Argus-specific state, snapshots, and working files.
- `argus/logs/`: Argus-specific logs and audit trail.
- `argus/ARGUS.md`: Policy and behavior contract for Argus.
- `.env`: Shared environment file at the agent root so both core runtime and Argus can read the same secrets and overrides.

Keep Argus lighter than core `src/` in implementation footprint, but more agentic in decision-making.

## Build And Dependency Rules

- Put Python project metadata in the agent root `pyproject.toml`.
- Add a root `BrewFile` only when OS-level packages are truly required.
- Prefer one shared root `pyproject.toml` for the agent; do not create a second Python project file for Argus unless it is intentionally becoming a separately managed runtime.
- Keep a single root `BrewFile` if OS-level dependencies are needed; do not duplicate Brewfiles across core and Argus unless the environments are intentionally diverging.
- Keep dependency scopes minimal and purpose-driven.
- Do not mix Argus dependencies into core runtime unless explicitly shared and justified.

## Scheduling Rules

If periodic execution is needed:

- Prefer explicit schedule definitions in either `src/launchd/` or `src/crontab.txt`.
- Keep schedule definitions versioned with the agent code.
- Ensure logs route to the correct domain (`logs/` for core, `argus/logs/` for Argus jobs).

## Argus Behavior Model

Argus is an agentic manager/owner layer that wakes periodically, gathers evidence, reasons about options, and drives improvements.

Argus should operate in this loop:

1. **Observe**: Inspect recent logs, system signals, and test outcomes.
2. **Diagnose**: Identify root causes, classify severity, and estimate impact.
3. **Plan**: Propose a prioritized improvement plan (quick wins first, then deeper fixes).
4. **Act**: Apply safe, scoped remediations directly when confidence is high.
5. **Verify**: Re-run targeted checks/tests and compare before/after signals.
6. **Report**: Write decisions, rationale, and outcomes to `argus/logs/`.

Argus should:

- Gather enough context before acting (avoid single-signal decisions).
- Prefer plan-first behavior over immediate patching.
- Escalate with a recommended plan when confidence is low or blast radius is high.
- Follow constraints, permissions, and escalation policy in `argus/ARGUS.md`.

Argus must avoid uncontrolled or broad changes. Keep fixes scoped, testable, reversible, and auditable.

## Implementation Workflow

When applying this skill, follow this sequence:

1. Confirm current structure and identify drift from the canonical layout.
2. Create or align core folders (`src`, `tests`, `data`, `logs`).
3. Ensure `src/pyproject.toml` exists and is valid.
4. Add schedule artifacts if periodic runs are required.
5. Create or align `argus/` with `ARGUS.md`, `src`, `data`, `logs`.
6. Separate responsibilities so Argus support code does not pollute core runtime code.
7. Validate with tests and a short operational smoke check.

## Output Expectations

When delivering changes using this skill:

- Provide a concise summary of structural changes.
- List created/modified files by purpose.
- Call out scheduling behavior and log destinations.
- Call out Argus guardrails from `argus/ARGUS.md`.
- Note any remaining risks or follow-up tasks.
