"""Classifier backend interface.

A pluggable `Backend` lets the host pick the strongest classifier it can run:

  * Tier 1 (macOS)  — Apple Foundation Models (vision).
  * Tier 2 (Windows)— bundled small VLM (FastVLM 0.5B) via ONNX Runtime.
  * Tier 3 (any OS) — heuristic: frontmost app + window title + YOLO face count.

Concrete backends arrive in later milestones (M1/M2). This module defines only
the interface and the small data carriers, so it stays import-clean everywhere.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Context:
    """Inputs handed to a backend for a single classification."""

    frontmost_app: Optional[str] = None
    window_title: Optional[str] = None
    face_count: int = 0
    image_bytes: Optional[bytes] = None  # capture, discarded by caller after use


@dataclass(frozen=True)
class Decision:
    """A backend's verdict. Maps directly onto the output log contract."""

    running: str = "unknown"  # "yes" | "no" | "unknown"
    focused: Optional[str] = None  # "yes" | "no" | None (omitted)
    note: str = ""


class BackendUnavailable(RuntimeError):
    """Raised when a backend cannot run on the current host (missing model, etc.)."""


class Backend(ABC):
    """Abstract classifier backend."""

    name: str = "abstract"

    @abstractmethod
    def classify(self, context: Context) -> Decision:
        """Classify a single context into a Decision."""
        raise NotImplementedError
