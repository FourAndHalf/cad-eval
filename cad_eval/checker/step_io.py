"""STEP file loading, kernel-agnostic checker boundary."""
from __future__ import annotations

from pathlib import Path

import cadquery as cq


def load_step(path: str | Path) -> cq.Shape:
    """Load a STEP file and return its top-level shape (may be a Compound)."""
    result = cq.importers.importStep(str(path))
    return result.val()
