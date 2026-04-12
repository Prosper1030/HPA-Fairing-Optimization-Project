"""
Helpers for loading OpenVSP across different installation layouts.

This project was originally written against a Windows setup where
`import openvsp as vsp` worked directly. On macOS newer OpenVSP releases ship
Python packages under nested directories such as:

    OpenVSP-3.45.3-MacOS/python/openvsp
    OpenVSP-3.45.3-MacOS/python/openvsp_config

Those layouts require a small amount of path and config setup before the core
module can be imported.
"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Iterable, List

_LOADED_VSP = None


def _unique_paths(paths: Iterable[Path]) -> List[Path]:
    seen = set()
    result = []

    for path in paths:
        resolved = path.expanduser()
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        result.append(resolved)

    return result


def _candidate_python_roots() -> List[Path]:
    candidates = []

    env_python = os.environ.get("OPENVSP_PYTHON_PATH")
    if env_python:
        candidates.append(Path(env_python))

    env_app = os.environ.get("OPENVSP_APP")
    if env_app:
        app_path = Path(env_app).expanduser()
        if app_path.is_dir():
            candidates.append(app_path / "Contents" / "Resources" / "python")
            candidates.append(app_path / "python")

    candidates.extend(
        [
            Path("/Applications/OpenVSP.app/Contents/Resources/python"),
            Path("/Applications/OpenVSP.app/python"),
            Path.home() / "Applications" / "OpenVSP.app" / "Contents" / "Resources" / "python",
            Path.home() / "Applications" / "OpenVSP.app" / "python",
        ]
    )

    for base_dir in [Path("/Volumes"), Path("/Applications"), Path.home() / "Applications"]:
        if not base_dir.exists():
            continue

        for release_dir in base_dir.glob("*/Applications/OpenVSP*-MacOS"):
            candidates.append(release_dir / "python")

        for release_dir in base_dir.glob("OpenVSP*-MacOS"):
            candidates.append(release_dir / "python")

    # If the current PYTHONPATH already contains an OpenVSP location, reuse it.
    for entry in os.environ.get("PYTHONPATH", "").split(":"):
        if not entry:
            continue
        path = Path(entry)
        if "openvsp" in entry.lower():
            candidates.append(path)
            candidates.append(path.parent)

    return _unique_paths(candidates)


def _path_entries_for_root(root: Path) -> List[Path]:
    entries = []

    if not root.exists():
        return entries

    if (root / "openvsp.py").exists() or (root / "openvsp" / "__init__.py").exists():
        entries.append(root)

    if (root / "openvsp" / "openvsp" / "__init__.py").exists():
        entries.append(root / "openvsp")

    if (root / "openvsp_config" / "openvsp_config" / "__init__.py").exists():
        entries.append(root / "openvsp_config")

    return _unique_paths(entries)


def _purge_openvsp_modules():
    for module_name in list(sys.modules):
        if module_name == "openvsp" or module_name.startswith("openvsp.") or module_name == "openvsp_config":
            sys.modules.pop(module_name, None)


def _prepare_openvsp_config(ignore_imports: bool):
    try:
        openvsp_config = importlib.import_module("openvsp_config")
    except ModuleNotFoundError:
        return

    if hasattr(openvsp_config, "LOAD_GRAPHICS"):
        openvsp_config.LOAD_GRAPHICS = False
    if hasattr(openvsp_config, "LOAD_FACADE"):
        openvsp_config.LOAD_FACADE = False
    if hasattr(openvsp_config, "LOAD_MULTI_FACADE"):
        openvsp_config.LOAD_MULTI_FACADE = False
    if ignore_imports and hasattr(openvsp_config, "_IGNORE_IMPORTS"):
        openvsp_config._IGNORE_IMPORTS = True


def load_openvsp(ignore_imports: bool = True):
    """Load and cache the OpenVSP Python module."""
    global _LOADED_VSP

    if _LOADED_VSP is not None and hasattr(_LOADED_VSP, "ClearVSPModel"):
        return _LOADED_VSP

    errors = []

    for root in _candidate_python_roots():
        entries = _path_entries_for_root(root)
        if not entries:
            continue

        _purge_openvsp_modules()
        importlib.invalidate_caches()

        for entry in reversed(entries):
            entry_str = str(entry)
            if entry_str not in sys.path:
                sys.path.insert(0, entry_str)

        try:
            _prepare_openvsp_config(ignore_imports=ignore_imports)
            module = importlib.import_module("openvsp")
            if hasattr(module, "ClearVSPModel"):
                _LOADED_VSP = module
                return module
            errors.append(f"{root}: imported openvsp without core API symbols")
        except Exception as exc:  # pragma: no cover - platform-specific diagnostics
            errors.append(f"{root}: {type(exc).__name__}: {exc}")

    message = "Unable to load OpenVSP. Tried roots:\n- " + "\n- ".join(
        errors or [str(root) for root in _candidate_python_roots()]
    )
    raise RuntimeError(message)
