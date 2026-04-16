"""
Shared bootstrap helpers for user-facing scripts.

This keeps the project-root and src-path setup consistent across CLI entry
points, without changing their runtime behavior.
"""

from __future__ import annotations

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"


def ensure_src_path() -> Path:
    src_path = str(SRC_ROOT)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)
    return PROJECT_ROOT
