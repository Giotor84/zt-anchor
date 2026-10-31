"""Abstention policy: a field is filled only with enough evidence; otherwise it goes to review or stays empty.

Three outcomes, never a silent guess:
- ACCEPTED      value anchored in the source, value inside the quote, confidence above the bar;
- NEEDS_REVIEW  plausible but not proven (ambiguous anchor, value not in the quote, middle confidence);
- ABSTAINED     no value, quote not in the source, or confidence too low.

Model and OCR scores are not probabilities: thresholds must be set on a frozen holdout (see ``holdout``),
not taken at face value.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .anchor import AnchorStatus, CheckedClaim


class Status(str, Enum):
    ACCEPTED = "accepted"
    NEEDS_REVIEW = "needs_review"
    ABSTAINED = "abstained"


@dataclass(frozen=True)
class Policy:
    accept_confidence: float = 0.90
    review_confidence: float = 0.60
    require_anchor: bool = True
    require_value_in_quote: bool = True


@dataclass
class Decision:
    field: str
    value: Any
    status: Status
    reasons: list[str] = field(default_factory=list)

    @property
    def filled(self) -> Any:
        """The value only when accepted; None otherwise. Use this to write outputs."""
        return self.value if self.status is Status.ACCEPTED else None

    def cell(self, review_label: str = "DA VERIFICARE") -> Any:
        """Spreadsheet-friendly: value, review label, or empty."""
        if self.status is Status.ACCEPTED:
            return self.value
        return review_label if self.status is Status.NEEDS_REVIEW else ""


def decide(
    field_name: str,
    value: Any,
    *,
    confidence: Optional[float] = None,
    checked: Optional[CheckedClaim] = None,
    policy: Policy = Policy(),
) -> Decision:
    reasons: list[str] = []
    if value is None or value == "":
        return Decision(field_name, None, Status.ABSTAINED, ["no value"])

    status = Status.ACCEPTED
    if policy.require_anchor:
        st = checked.status if checked else None
        if st is None or st in (AnchorStatus.NOT_FOUND, AnchorStatus.SOURCE_UNKNOWN, AnchorStatus.NO_QUOTE):
            why = st.value if st else "no anchor check"
            return Decision(field_name, value, Status.ABSTAINED, [f"not anchored: {why}"])
        if st is AnchorStatus.AMBIGUOUS:
            status = Status.NEEDS_REVIEW
            reasons.append(f"quote found {checked.anchor.occurrences} times")
    if policy.require_value_in_quote and checked is not None and checked.value_in_quote is False:
        status = Status.NEEDS_REVIEW
        reasons.append("value not inside the quoted span")
    if confidence is not None:
        if confidence < policy.review_confidence:
            return Decision(field_name, value, Status.ABSTAINED, reasons + [f"confidence {confidence:.2f} too low"])
        if confidence < policy.accept_confidence:
            status = Status.NEEDS_REVIEW
            reasons.append(f"confidence {confidence:.2f} below {policy.accept_confidence:.2f}")
    return Decision(field_name, value, status, reasons)
