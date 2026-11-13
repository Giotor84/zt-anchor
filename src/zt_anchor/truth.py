"""Truth labels for reports: say how each statement is known, so synthetic results are never sold as live ones.

- VERIFIED_SYNTHETIC  checked by a test or a run on synthetic data (evidence required);
- VERIFIED_LIVE       checked on the real system or real data (evidence required);
- REPORTED_EXTERNAL   reported by someone else, not re-run here;
- VERIFY_LIVE         expected to hold, still to be checked on the real system;
- PROPOSED            a plan or an idea;
- UNAVAILABLE         cannot be known with what is available.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Optional


class Truth(str, Enum):
    VERIFIED_SYNTHETIC = "VERIFIED_SYNTHETIC"
    VERIFIED_LIVE = "VERIFIED_LIVE"
    REPORTED_EXTERNAL = "REPORTED_EXTERNAL"
    VERIFY_LIVE = "VERIFY_LIVE"
    PROPOSED = "PROPOSED"
    UNAVAILABLE = "UNAVAILABLE"


_NEEDS_EVIDENCE = {Truth.VERIFIED_SYNTHETIC, Truth.VERIFIED_LIVE, Truth.REPORTED_EXTERNAL}


@dataclass(frozen=True)
class Statement:
    text: str
    label: Truth
    evidence: Optional[str] = None   # test name, command, file, or who reported it

    def __post_init__(self) -> None:
        if self.label in _NEEDS_EVIDENCE and not (self.evidence and self.evidence.strip()):
            raise ValueError(f"{self.label.value} needs evidence: {self.text!r}")


def render_markdown(statements: Iterable[Statement], title: str = "Status") -> str:
    """A table grouped in label order, so the reader sees first what is proven and last what is not."""
    order = list(Truth)
    rows = sorted(statements, key=lambda s: order.index(s.label))
    lines = [f"## {title}", "", "| label | statement | evidence |", "|---|---|---|"]
    lines += [f"| `{s.label.value}` | {s.text} | {s.evidence or ''} |" for s in rows]
    return "\n".join(lines) + "\n"
