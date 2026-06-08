#!/usr/bin/env python3
"""Pluggable classifier backends for Focus Coach Native.

The service captures a frame and gathers cheap OS context (frontmost app name,
window title, optional YOLO objects), then hands it to a Backend that returns a
readout dict:

    {"category": "working"|"not_working"|"unknown",
     "focused": bool,
     "activity": "<short label>",
     "summary": "<one sentence, no personal content>"}

Tiers (best-available per platform, graceful fallback):

  Tier 1  macOS    AppleVisionBackend   -> Apple Foundation Models (vision).
                                            Native Swift in the shipped app;
                                            not callable from this Python proto.
  Tier 2  Windows  OnnxVlmBackend       -> small VLM (e.g. FastVLM) via ONNX
                                            Runtime, bundled in the app.
  Tier 3  any      HeuristicBackend     -> frontmost app + window title + YOLO
                                            faces. No LLM. Always works. Runs
                                            today, cross-platform.

  dev     any      OllamaBackend        -> local Ollama vision model. Dev-only
                                            convenience for iterating on prompts;
                                            NOT a shipping target.

Each backend implements: classify(frame_path: Path, ctx: dict) -> dict
where ctx = {"app": str, "title": str, "objects": list[str]}.
"""

from __future__ import annotations

import base64
import io
import json
import re
from pathlib import Path

# Pillow + requests are only needed by some backends; import lazily where heavy.


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _empty_readout(category="unknown", activity="unknown", summary="", focused=False):
    return {"category": category, "focused": focused,
            "activity": activity, "summary": summary}


def parse_readout(raw: str) -> dict:
    """Tolerantly pull a readout JSON object out of a model's text response."""
    out = _empty_readout()
    out["_raw"] = raw
    m = re.search(r"\{.*\}", raw.strip(), re.DOTALL)
    if m:
        try:
            obj = json.loads(m.group(0))
            cat = str(obj.get("category", "unknown")).lower()
            if cat not in ("working", "not_working", "unknown"):
                cat = "unknown"
            out["category"] = cat
            out["focused"] = bool(obj.get("focused", cat == "working"))
            out["activity"] = str(obj.get("activity", "unknown"))[:40]
            out["summary"] = str(obj.get("summary", ""))[:200]
        except json.JSONDecodeError:
            pass
    return out


# ---------------------------------------------------------------------------
# Tier 3 — heuristic (no model). Cross-platform, always available.
# ---------------------------------------------------------------------------

# App-name substrings (lowercased) -> strong work signal.
WORK_APPS = {
    "code", "xcode", "terminal", "iterm", "intellij", "pycharm", "webstorm",
    "cursor", "visual studio", "sublime", "vim", "emacs", "nova", "zed",
    "slack", "mail", "spark", "outlook", "notion", "obsidian", "bear",
    "word", "excel", "powerpoint", "pages", "numbers", "keynote", "docs",
    "sheets", "figma", "sketch", "balsamiq", "zoom", "meet", "teams", "webex",
    "linear", "jira", "asana", "github", "sourcetree", "postman", "tableplus",
    "pgadmin", "datagrip", "preview", "acrobat", "calendar", "fantastical",
}
# App-name substrings -> strong distraction signal.
DISTRACT_APPS = {
    "netflix", "hulu", "disney", "prime video", "sling", "twitch", "tv",
    "spotify", "music", "podcasts", "steam", "game", "discord", "whatsapp",
    "messages", "tiktok", "instagram",
}
# Browsers are ambiguous — decide from the window title.
BROWSERS = {"safari", "chrome", "firefox", "edge", "arc", "brave", "opera"}
TITLE_WORK = {
    "github", "gitlab", "stack overflow", "stackoverflow", "jira", "linear",
    "docs.", "developer.", "notion", "confluence", "google docs", "sheets",
    "localhost", "pull request", "documentation", "api reference", "aws",
    "console", "dashboard",
}
TITLE_DISTRACT = {
    "youtube", "reddit", "twitter", "x.com", "facebook", "instagram", "tiktok",
    "netflix", "twitch", "espn", "amazon", "ebay", "news", "9gag", "imgur",
}


def _match(text: str, needles: set[str]) -> bool:
    t = text.lower()
    return any(n in t for n in needles)


class HeuristicBackend:
    """Classify from frontmost app + window title + YOLO faces. No LLM."""

    name = "heuristic"

    def classify(self, frame_path: Path, ctx: dict) -> dict:
        app = (ctx.get("app") or "").strip()
        title = (ctx.get("title") or "").strip()
        objects = ctx.get("objects") or []
        app_l = app.lower()
        person_count = sum(1 for o in objects if o == "person")

        # Multiple faces on screen -> almost certainly a video meeting.
        if person_count >= 2:
            return _empty_readout("working", "video meeting",
                                  f"{app or 'app'} showing multiple participants",
                                  focused=True)

        if _match(app_l, WORK_APPS):
            return _empty_readout("working", "focused work",
                                  f"using {app}", focused=True)

        if _match(app_l, DISTRACT_APPS):
            return _empty_readout("not_working", "leisure",
                                  f"using {app}", focused=False)

        if any(b in app_l for b in BROWSERS):
            if _match(title, TITLE_DISTRACT):
                return _empty_readout("not_working", "browsing (leisure)",
                                      "leisure site in browser", focused=False)
            if _match(title, TITLE_WORK):
                return _empty_readout("working", "browsing (work)",
                                      "work site in browser", focused=True)
            return _empty_readout("unknown", "browsing",
                                  f"{app}: unclassified page", focused=False)

        # No signal we trust.
        label = f"using {app}" if app else "no foreground app detected"
        return _empty_readout("unknown", "unclassified", label, focused=False)


# ---------------------------------------------------------------------------
# dev — Ollama vision model. Iterating on prompts only; not a shipping target.
# ---------------------------------------------------------------------------

VLM_PROMPT = (
    "You are analyzing a single screenshot of a person's computer screen to "
    "produce a short activity readout. Context hints: frontmost app is "
    "'{app}'; window title is '{title}'; an object detector found: {objects}. "
    "Decide whether the person appears to be doing focused work (coding, "
    "writing, reading work material, email, video meeting, design/professional "
    "tools) versus not working (social media, video streaming, games, shopping, "
    "idle desktop). Respond with ONLY a JSON object, no prose, no markdown:\n"
    '{{"category": "working" | "not_working" | "unknown", '
    '"focused": true | false, '
    '"activity": "<2 to 4 word label>", '
    '"summary": "<one short sentence describing the activity, NOT the personal '
    'content on screen>"}}\n'
    "Do not transcribe names, messages, code, or any personal text. Use "
    '"unknown" only if the screen is unreadable.'
)

DOWNSCALE_LONG_EDGE = 1024


class OllamaBackend:
    name = "ollama"

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _downscale_b64(self, path: Path) -> str:
        from PIL import Image
        with Image.open(path) as im:
            im = im.convert("RGB")
            w, h = im.size
            scale = DOWNSCALE_LONG_EDGE / max(w, h)
            if scale < 1:
                im = im.resize((int(w * scale), int(h * scale)))
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("ascii")

    def classify(self, frame_path: Path, ctx: dict) -> dict:
        import requests
        prompt = VLM_PROMPT.format(
            app=ctx.get("app") or "unknown",
            title=ctx.get("title") or "unknown",
            objects=", ".join(ctx.get("objects") or []) or "none",
        )
        payload = {
            "model": self.model,
            "prompt": prompt,
            "images": [self._downscale_b64(frame_path)],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
        }
        resp = requests.post(f"{self.base_url}/api/generate", json=payload, timeout=120)
        resp.raise_for_status()
        return parse_readout(resp.json().get("response", ""))


# ---------------------------------------------------------------------------
# Tier 1 / Tier 2 — production backends (stubs; implemented in the native app).
# ---------------------------------------------------------------------------

class AppleVisionBackend:
    """macOS: Apple Foundation Models (vision). Implemented in Swift in the
    shipped app — this Python stub exists to document the interface and to fail
    loudly if selected from the prototype."""

    name = "apple"

    def classify(self, frame_path: Path, ctx: dict) -> dict:
        raise NotImplementedError(
            "AppleVisionBackend runs via the Foundation Models framework in the "
            "native Swift app; it is not callable from the Python prototype. "
            "Use --backend heuristic (or ollama) for prototyping.")


class OnnxVlmBackend:
    """Windows/cross-platform: small VLM (e.g. FastVLM) via ONNX Runtime,
    bundled in the app. Stub for now."""

    name = "onnx"

    def classify(self, frame_path: Path, ctx: dict) -> dict:
        raise NotImplementedError(
            "OnnxVlmBackend (bundled FastVLM via ONNX) is not wired up yet. "
            "Use --backend heuristic (or ollama) for prototyping.")


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_backend(name: str, *, ollama_url: str, model: str):
    name = (name or "heuristic").lower()
    if name == "heuristic":
        return HeuristicBackend()
    if name == "ollama":
        return OllamaBackend(ollama_url, model)
    if name == "apple":
        return AppleVisionBackend()
    if name == "onnx":
        return OnnxVlmBackend()
    raise SystemExit(f"Unknown backend '{name}'. "
                     f"Choose: heuristic, ollama, apple, onnx.")
