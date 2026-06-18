# Fomi-for-Me — Design Document

**Status:** Draft v0.3 for PM review (v0.2: deterrent ladder + justification flow; v0.3: Python is interim only — notifications move to a web-services gateway, the first v2 server piece) · **Author:** Engineering (Claude) · **Date:** 2026-06-10
**Repo:** `~/PROJ/ASHANBH/personal_agents/shanfomi_fable/fomi for me`

---

## 1. Problem & Goals

We use fomilab.ai's Fomi today (camera attention check + screen work/distraction check). It works, but has four limitations we will fix by building our own **native macOS desktop app**:

| # | Limitation today | Goal |
|---|---|---|
| 0 | Camera + screen monitoring works OK | Keep, but run fully on-device |
| 1 | Must manually start a session and declare the task | **Zero-config**: starts at login, infers work vs. not-work from persona presets (engineer / accountant / doctor) |
| 2 | No social accountability | **Auto-send sanitized daily digests** to accountability partners |
| 3 | No way to improve behavior collaboratively | **Coach chat window** backed by a local LLM that sees your history and can adjust the rules with you |
| 4 | (future) No server component | Server sync where **PII/embarrassing detail never leaves the desktop**, and whatever is sent is inspectable and erasable |

### Non-goals (v1)
Windows build (design keeps a port path open); blocking/locking apps (we observe and nudge, not enforce); mobile companion; multi-user.

---

## 2. Hard Privacy Invariants

These are product invariants, enforced by architecture, not by policy text:

1. **Ephemeral perception.** Camera frames and screen frames live only in memory, are classified, and are discarded. They are never written to disk, never logged, never transmitted. (PM requirement: "this data should never be stored, only classified and used.")
2. **Derived events only.** The only thing persisted is a small structured event: `(timestamp, signal_type, category, confidence)`. No raw pixels, no OCR dumps.
3. **Sensitive-category collapse.** Anything classified into a sensitive bucket (adult content, health, finance-personal) is stored only as `category=private-nonwork` or `private-work`. The specific site/app name is *not* persisted. "Dude watched X for 3 hours" is representable only as "3h non-work." This collapse happens **before** the write to SQLite, so even local history can't embarrass.
4. **All inference local.** YOLO-class vision models and the LLM run on-device. No cloud inference in the perception path.
5. **Egress allowlist.** The only bytes that ever leave the machine are (a) the sanitized digest email and (b) future Tier-B server sync. Both are generated from the already-sanitized event store, both are human-readable, and both are logged verbatim to `data/egress/` so you can always see exactly what left.

---

## 3. Architecture Overview

Native macOS menu-bar app (Swift/SwiftUI, runs as Login Item) + a small Python support layer reusing existing argus infrastructure.

**Python is interim, not a product dependency (PM decision, 2026-06-10).** End users must not need a Python install. The Python layer below is acceptable for our own machine during M1–M5. The productized delivery path for notifications (email, Slack, later WhatsApp/iMessage-style channels) is a thin **notification web-services layer**: the Swift app POSTs the already-sanitized digest payload (Tier B only — same redaction contract as §3.5) to the gateway, which handles SMTP/Slack API delivery, retries, and partner preferences. This gateway is the first concrete piece of the v2 server (§3.7). The app itself stays pure Swift with zero runtime dependencies.

```
┌─────────────────────────── Fomi-for-Me.app (Swift) ───────────────────────────┐
│  Perception (in-memory only)            Classification cascade                │
│  ┌──────────────────────────┐           ┌──────────────────────────────────┐  │
│  │ ScreenCaptureKit frames  │──frames──▶│ T0 rules: bundle-id/domain lists │  │
│  │ NSWorkspace frontmost app│──meta───▶ │ T1 vision: CoreML YOLO + Vision  │  │
│  │ AX/AppleScript: tab URL  │           │ T2 local LLM: ambiguous cases    │  │
│  │ AVFoundation camera      │──frames──▶│    (window title + on-screen     │  │
│  └──────────────────────────┘           │     text, Foundation Models)     │  │
│         frames dropped ───────X         └───────────────┬──────────────────┘  │
│                                                         │ sanitized events    │
│  Session engine (auto start/stop, idle)  ◀──────────────┤                     │
│  Coach chat window (local LLM + tools)   ◀──────────────┤                     │
│                                                         ▼                     │
│                                   SQLite event store (events, sessions,       │
│                                   rules, coach notes — no raw data)            │
└────────────────────────────────────────────┬───────────────────────────────────┘
                                             │ read-only
              ┌──────────────────────────────┴───────────────────────┐
              │ Python support layer (reuses ~/…/personal_agents)     │
              │ • digest builder → argus_common/notify_via_email.py          │
              │ • argus_focusmon coach email (swap fomi_db → our DB)  │
              │ • Argus monitoring of the agent itself                │
              └───────────────────────────────────────────────────────┘
```

### 3.1 Perception layer (Swift)

- **Screen:** ScreenCaptureKit (macOS 12.3+; the modern permission-aware capture API). Low rate — 1 frame / 10–20 s, downscaled. Requires Screen Recording permission once.
- **App metadata:** `NSWorkspace.frontmostApplication` + window title; browser URL via Accessibility/AppleScript (Safari, Chrome). Metadata is the *cheap* signal; most ticks never need a frame.
- **Camera:** AVFoundation at low fps in short bursts (e.g., 3 s every 60 s), only while a work session is active. Used solely to answer: *person present? looking at screen? phone in hand?*
- Frames are processed and released inside the capture callback. No frame ever reaches the persistence layer — enforced by module boundary (the store's API only accepts the `Event` struct).

### 3.2 Classification cascade — cheap first, smart last

- **Tier 0 — rules (≈90% of ticks, <1 ms):** persona presets as editable YAML/JSON rule packs:
  - *Engineer:* VS Code, Xcode, Terminal, Cursor, GitHub, Stack Overflow, localhost, Google Meet/Zoom/Slack → work. Instagram, TikTok, Netflix → not-work.
  - *Accountant:* Excel, QuickBooks, TurboTax, bank portals → work.
  - *Doctor:* EHR (Epic et al.), UpToDate, telehealth → work. **Doctor persona forces metadata-only mode for EHR apps — no screen frames captured at all while an EHR is frontmost (PHI).**
  - Meetings are work by default (camera "person absent" is not a distraction while in Meet/Zoom).
- **Tier 1 — on-device vision:** YOLO-class detector compiled to Core ML (ANE-accelerated) for camera frames: person / phone-in-hand / gaze-away. Apple Vision framework for face presence + roll/yaw as a cheap gaze proxy.
- **Tier 2 — local LLM (ambiguous cases only, e.g., YouTube):** window title + OCR'd text snippets (Vision OCR, in-memory) prompted to the on-device **Apple Foundation Models** framework (macOS 26+; the 2026 model accepts images directly, so we can pass the downscaled frame itself without it ever leaving the process). Fallback for older macOS or stronger judgment: MLX/Ollama running Qwen-class small model locally. Output: `{category, confidence, reason}` — the reason string is shown in the UI but stored only for non-sensitive categories.
- Cascade contract: T0 answers if confident; else T1/T2. LLM verdicts on repeated (app, domain) pairs are **memoized into new T0 rules**, so the system gets cheaper and more personal over time — and the coach can review/edit these learned rules with you.

### 3.3 Session engine — no manual start

- Starts monitoring at login (Login Item). A "work session" is *inferred*: ≥N consecutive work-classified ticks opens a session; ≥M minutes idle (no input events) or sustained not-work closes it.
- Manual override remains: pause button (meeting privacy, demos), per-app permanent exclusions.

**Deterrent ladder with justification (replaces fomilab's surprise tomato).** The splat is effective — we keep it, but make it fair and informative:

1. **Warn (T+0):** subtle nudge — menu-bar icon turns orange + small banner: *"Looks like not-work (social video). Tomato incoming in 60s."*
2. **Countdown (T+60s):** corner overlay with visible countdown and a **one-line justification box**. User types e.g. *"YouTube video about linear algebra — studying"* and hits Enter; takes <5 seconds.
   - Justification is fed to the T2 local LLM **together with the current screen context** to sanity-check it (title "Taylor Swift — official video" + claim "linear algebra" → rejected with a smirk; plausible claim → accepted).
   - Accepted → tick reclassified as work, deterrent cancelled, and the (app, domain/title-pattern, justification) is memoized as a candidate T0 rule.
   - Ignored or rejected → step 3.
3. **Splat (T+90s):** full tomato (or rotating deterrents — screen desaturation, escalating splats — configurable). Still never blocks input; we deter, not enforce.

Every justification (accepted or rejected) is stored in the `justifications` table — these are user-typed, deliberate statements, so they're persisted verbatim (not subject to sensitive-collapse) and become first-class coach material.

### 3.4 Event store (SQLite)

Tables: `events` (tick classifications), `sessions` (derived), `rules` (T0 packs + learned rules + audit of who changed what: user via coach vs. memoized), `justifications` (timestamp, user-typed claim, screen-context summary, accepted/rejected, linked goal), `goals` (daily intentions, set via coach chat or quick-entry), `coach_notes` (chat summaries, commitments), `egress_log` (verbatim copies of everything sent off-device).

Data lifecycle:

| Signal | Retention |
|---|---|
| Camera/screen frames | **0 — never persisted** |
| Window title / URL | In-memory for classification; persisted only for non-sensitive categories, pruned after 30 days |
| Tick events (category, confidence) | 90 days local |
| Session aggregates | Indefinite local (it's your history; coach uses it) |
| Digest emails / server sync payloads | Copy in `egress_log`, erasable |

### 3.5 Accountability digests (auto-send)

- Daily email to configured partners, auto-sent (PM decision) via the existing **`argus_common/notify_via_email.py`** + SMTP creds in `focusmon/.env`. Aligns with the existing noon/6pm partner cadence rather than adding a third stream.
- **Sanitization contract:** digest contains *only* category-level aggregates and streaks — e.g., "Focused 5h 40m (best streak 92 min) · Distracted 1h 10m · 14 drift events · top distraction class: social video." Never app names, titles, URLs, or anything from a `private-*` bucket beyond its contribution to the not-work total.
- Digest template is a fixed schema rendered from aggregates — the LLM never free-writes partner-facing text, so it cannot leak specifics.
- Partner config: name, email, schedule, and digest verbosity (stats-only vs. stats+trend chart, reusing the sparkline/hour-grid HTML style already used by the focusmon coach emails).

### 3.6 Coach chat

- Chat pane in the app, backed by the same local LLM, with tools: `read_history(range)` (aggregates + non-sensitive events), `propose_rule_change`, `set_commitment`, `configure_digest`.
- Behavior model: collaborative, not punitive — review yesterday, name one pattern, agree on one experiment, follow up next day. (Same philosophy as the existing argus_focusmon morning-coach email; that email pipeline keeps working and simply reads our DB instead of fomilab's.)
- **Goal alignment via justifications.** Justifications make "work" two-dimensional: *work-on-goal* vs. *work-off-goal*. If the day's goal was "clear all tickets" but justifications show 6h of "linear algebra videos — studying," the coach doesn't scold (it *was* work) — it surfaces the drift: *"All legitimate, but zero ticket progress. What's tomorrow's plan — tickets first, lectures after 4pm?"* and records the agreed plan as tomorrow's goal + a commitment to follow up on.
- Repeated accepted justifications for the same pattern → coach proposes promoting it to a permanent rule; repeated rejected ones → coach raises it as a self-deception pattern worth discussing.
- Rule changes proposed by the coach require one-tap user confirmation; all changes audited in `rules`.

### 3.7 Server component (v2, design now / build later)

- **Tier A (never leaves desktop):** frames (never exist anyway), titles, URLs, rule contents, chat transcripts, anything `private-*`.
- **Tier B (syncable):** the same aggregates the digest may contain — daily category durations, streaks, drift counts. Nothing finer-grained than the digest.
- Server stores Tier B keyed to an account; client keeps `egress_log` of every payload. UI: "View everything the server has" (renders server copy, byte-for-byte inspectable) and "Erase" (delete API + local proof-of-deletion receipt). Sync is opt-in, off by default.
- Use cases unlocked: cross-device history, partner web dashboard, coach memory roaming.
- **First server milestone = notification gateway** (replaces the interim Python digest sender): receives only digest-grade Tier-B payloads, delivers to email/Slack, keeps a copy the user can view and erase — same `egress_log` contract on both ends.

---

## 4. Repo Layout (bb-agentic canonical, adapted for a native app)

```
fomi for me/
  .env                    # SMTP, partner emails, persona
  app/                    # Xcode project — Swift core (perception, cascade, UI)
  src/                    # Python support: digest builder, db reader (fomi4me_db.py)
    launchd/              # digest schedule, agent jobs
  tests/                  # Swift unit tests via xcodebuild; pytest for src/
  data/                   # SQLite event store, egress_log/
  logs/
  argus/
    ARGUS.md              # monitoring contract: app alive? perception permissions healthy?
    src/  data/  logs/    #   digest sent? DB growing? classification drift?
  pyproject.toml
```

Argus watches the agent (capture permission revoked, app crashed, digest failed to send, T2 fallback rate climbing) and self-heals or escalates via the existing notifiers (desktop, iMessage, email).

---

## 5. Milestones (each ends in a demo to PM)

| M | Deliverable | Demo |
|---|---|---|
| M1 | Menu-bar app: metadata-only monitoring + persona T0 rules + auto-sessions + SQLite | Live: open VS Code vs. Instagram, watch session state flip; show DB has no titles for private buckets |
| M2 | Screen frames + Vision OCR + T2 local LLM for ambiguous (YouTube test) + deterrent ladder with justification box | YouTube lecture vs. music video classified correctly; type "linear algebra lecture" during countdown → tomato cancelled, rule learned; bogus justification → rejected, splat lands. Zero disk writes from perception |
| M3 | Camera presence + phone detection (Core ML YOLO) | Pick up phone during session → drift event; in Meet → no false positive |
| M4 | Digest pipeline auto-sending via argus notifier + egress_log viewer | Real email to a test partner; inspect/erase the egress log |
| M5 | Coach chat with rule-editing tools; focusmon coach email reads our DB | Chat: "YouTube was work yesterday, it was a conference talk" → rule updated with confirmation |

---

## 6. Risks & Open Questions for PM

1. **macOS version floor.** Foundation Models needs macOS 26+. Proposal: require macOS 26 for T2-via-Apple; ship Ollama fallback for older. OK?
2. **Distribution.** Screen Recording + always-on camera is hostile to App Store sandbox review. Proposal: Developer-ID notarized direct distribution (like fomilab's Windows build). OK?
3. **Camera duty cycle.** Always-on camera light may be socially awkward (office, patients). Default burst-sampling with a visible menu-bar indicator, persona-level off switch (doctors default camera-off?). Decide default per persona.
4. **Digest send-without-review tension.** Auto-send was chosen, but first 2 weeks could run in "review mode" (digest sent to *you* only) to validate the sanitizer before partners see anything. Recommend yes.
5. **Sensitive-category list.** What buckets collapse to `private-*`? Proposed: adult, health/medical-personal, personal finance, dating. PM to confirm.
6. **Swift vs. cross-platform shell.** Swift chosen for ANE/CoreML/ScreenCaptureKit access and low overhead. A Windows port later means a parallel perception layer (Windows Graphics Capture + ONNX/DirectML) behind the same event schema. Accepting that cost now.

---

## 7. Key References

- Fomi baseline: https://www.fomilab.ai/ (features, pricing; "locally anonymized before AI analysis, we do not store your data")
- Apple Foundation Models framework (on-device LLM, WWDC25; image input + provider extensions at WWDC26): https://developer.apple.com/documentation/FoundationModels · https://developer.apple.com/videos/play/wwdc2026/339/
- ScreenCaptureKit (capture + permission model): https://developer.apple.com/documentation/ScreenCaptureKit/capturing-screen-content-in-macos
- Existing in-house infra: `~/PROJ/ASHANBH/personal_agents/argus_common` (notifiers, argus_focusmon coach, fomi_db.py reader to be replaced by our own DB)
