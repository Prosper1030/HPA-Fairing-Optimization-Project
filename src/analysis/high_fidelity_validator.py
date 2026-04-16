"""
Reserved interface for future shortlist-level high-fidelity validation.

The project plans to use SU2 for final verification only. The fast proxy remains
the only production analysis path for now.
"""

from __future__ import annotations

from typing import Iterable, Mapping


class HighFidelityValidationNotReady(NotImplementedError):
    """Raised when a planned high-fidelity backend is not implemented yet."""


def validate_shortlist(
    candidates: Iterable[Mapping],
    *,
    backend: str = "su2",
) -> None:
    candidate_count = sum(1 for _ in candidates)
    if backend != "su2":
        raise ValueError(f"Unsupported high-fidelity backend: {backend}")
    raise HighFidelityValidationNotReady(
        f"SU2 shortlist validation is planned but not implemented yet. Received {candidate_count} candidate(s)."
    )
