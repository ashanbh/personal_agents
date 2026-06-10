# FomiForMe

Native macOS focus monitor — our replacement for fomilab.ai's Fomi.
See `DESIGN.md` (v0.3, PM-approved) for the full architecture.

**Milestone status: M1** — metadata-only monitoring, persona rules,
auto-sessions, SQLite, sanitized digest pipeline (interim Python). No screen
frames, no camera yet (M2/M3). No tomato yet (M2).

## Quick start

```bash
make build          # requires Xcode command-line tools (swift 5.9+)
make run            # menu-bar app: ⚪️ no session · 🟢 working · 🟠 drifting · ⏸ paused
make test           # pytest (python layer) + swift test (classifier, session engine)
```

First run prompts for **Automation** permission per browser (to read the
front tab's URL — metadata only). Denying it just means browser ticks classify
as `unknown`.

Digest (review mode is ON by default — it emails only you, never partners):

```bash
cp .env.example .env   # fill in PARTNER_EMAILS, REVIEW_RECIPIENT
make digest            # print today's digest + write egress copy (no send)
python3 src/digest_builder.py --send   # actually email it
make install-launchd   # auto-send daily at 18:00
```

## Privacy invariants (enforced, not promised)

- Only derived events are stored: `(ts, category, confidence, tier)` plus
  app/domain identifiers **except** for `private-*` categories, whose
  identifiers are stripped before the write (`Tick.sanitized()`, double-checked
  at the DB boundary in `EventStore.insert`).
- Partner digests are a fixed template over aggregates; `assert_sanitized()`
  hard-fails on URLs/domains/private markers; non-work specifics appear only
  as coarse classes ("social video"), never names.
- Everything that leaves the machine is archived verbatim in `data/egress/`.
- Argus audits the invariant (`argus/src/check_health.py`); a violation is
  sev-1: stop the app, quarantine the DB, escalate.

## Layout (bb-agentic)

```
app/        Swift package — the actual menu-bar app (zero runtime deps)
src/        interim Python: fomi4me_db.py reader, digest_builder.py, launchd/
tests/      pytest for the Python layer + rule-pack contracts
data/       SQLite default lives in ~/Library/Application Support/FomiForMe;
            egress/ holds verbatim copies of everything sent off-device
argus/      ARGUS.md contract + health checks
```

## Known M1 limitations

- YouTube is classified non-work for the engineer persona; M2's local-LLM
  tier + justification flow ("linear algebra lecture") makes it ambiguous-aware.
- Window titles are not read (metadata is app + browser-tab domain only).
- The deterrent ladder (warn → countdown+justify → tomato) lands in M2.
- Swift tests must run on macOS (`make test-swift`); CI sandbox runs only pytest.
