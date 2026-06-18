# Project status — FomiForMe (handoff document)

**Last updated:** 2026-06-10 by engineering (Claude). This file travels with the
repo so work can resume on any machine. Read `DESIGN.md` first, then this.

## Where things stand

| Item | State |
|---|---|
| DESIGN.md v0.3 | **PM-approved.** Includes deterrent ladder + justification flow (v0.2) and "Python is interim, notifications move to a web gateway" (v0.3) |
| M1 code | **Written, NOT yet compiled.** Swift never built (engineering sandbox is Linux; no Xcode). `make build` on a Mac is the next action |
| Python layer | Working. 14/14 pytest pass; digest + health-check smoke-tested end-to-end with synthetic data |
| Computer-use build attempt | User denied screen-control permission (Script Editor/Finder/Terminal) on 2026-06-10 — build must be run manually or permission re-granted |
| M2–M5 | Not started |

## Immediate next steps

1. On a Mac with Xcode CLT: `make build && make test && make run` (repo root).
   Fix any Swift compile errors — code is review-verified only.
2. M1 demo to PM: VS Code → 🟢, instagram.com in browser → 🟠 after ~60
   consecutive non-work ticks session closes; menu shows today's totals.
3. `cp .env.example .env`, fill PARTNER_EMAILS + REVIEW_RECIPIENT, then
   `make digest` (dry run) and `make install-launchd` (18:00 daily, review mode).
4. Then start M2: screen frames (ScreenCaptureKit) + Vision OCR + local LLM
   tier + deterrent ladder w/ justification box (DESIGN.md §3.3).

## Key decisions already made (don't re-litigate)

- PM relationship: engineering works autonomously; contact PM only for
  design/mockup reviews and demos, via `~/PROJ/ASHANBH/personal_agents/argus_common`
  notifiers (desktop/email/iMessage) or chat if active.
- Native desktop app is critical; Swift, menu-bar, zero runtime deps.
- Perception (camera/screen) is NEVER stored — classified in memory, dropped.
- Sensitive categories collapse to `private-*` with identifiers stripped
  BEFORE persistence (`Tick.sanitized()` + re-check in `EventStore.insert`).
- Digests auto-send but are fixed-template aggregates only;
  `assert_sanitized()` blocks URLs/domains/private markers. Review mode
  (self-only) is ON by default for the first ~2 weeks.
- Classification: YOLO-style local vision + local LLM (Apple Foundation
  Models, macOS 26+; Ollama fallback). Justifications are LLM-sanity-checked
  against screen context; accepted ones memoize into T0 rules.
- Python layer is interim scaffolding; product path = notification
  web-services gateway (first v2 server piece).

## Open PM questions (DESIGN.md §6)

macOS 26 floor · direct distribution vs App Store · camera default per
persona (doctors off?) · sensitive-category list confirmation.

## Repo map

```
DESIGN.md                 architecture (v0.3, approved)  ← source of truth
STATUS.md                 this file
app/                      Swift SPM menu-bar app (M1, uncompiled)
  Sources/FomiForMe/      main, AppDelegate, Poller, Classifier, RulePack,
                          SessionEngine, EventStore, BrowserURL, Models
  Sources/FomiForMe/Rules engineer/accountant/doctor/sensitive JSON packs
  Tests/FomiForMeTests/   Classifier + SessionEngine unit tests
src/                      fomi4me_db.py (reader, swaps in for argus
                          argus_focusmon/fomi_db.py), digest_builder.py,
                          launchd/ digest plist (18:00)
tests/                    pytest — all passing
argus/                    ARGUS.md contract + src/check_health.py
                          (privacy audit violation = sev-1)
scripts/m1_demo.sh        build+test+launch, logs to logs/build.log
Makefile                  build / run / test / digest / health / install-launchd
.env.example              copy to .env (PARTNER_EMAILS, REVIEW_RECIPIENT, …)
```

## Related external pieces

- `~/PROJ/ASHANBH/personal_agents/argus_common` — notifiers (email/iMessage/desktop),
  `argus_focusmon/` morning coach email (M5: point it at our DB via
  `src/fomi4me_db.py`), SMTP creds referenced from `focusmon/.env`.
- fomilab Fomi (`ai.fomilab.app`) still installed — being replaced by this.

## Conventions

- Tick interval 5 s (`Poller.tickIntervalS` must match `fomi4me_db.TICK_S`).
- DB default: `~/Library/Application Support/FomiForMe/fomi4me.sqlite`
  (override: `FOMI4ME_DB`).
- Everything that leaves the machine gets a verbatim copy in `data/egress/`.
- Milestones M1–M5 defined in DESIGN.md §5; each ends in a PM demo.
