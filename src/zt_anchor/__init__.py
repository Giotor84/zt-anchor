"""ZT Anchor — document AI that can say "I don't know".

Anchoring of every claim to the source, abstention instead of guessing, frozen-holdout evaluation, truth labels,
structured output with validation, deterministic contract lint and Italian normalisation.
"""
from .abstain import Decision, Policy, Status, decide
from .anchor import Anchor, AnchorStatus, CheckedClaim, Claim, Source, anchor_quote, check_claims
from .contract_lint import Finding, lint
from .holdout import HoldoutInvalidated, evaluate, fingerprint, freeze, load_frozen
from .it_normalize import find_amounts, flag, parse_amount, parse_date_it, words_to_number
from .structured import StructuredOutputError, extract_json, generate_structured, validate
from .truth import Statement, Truth, render_markdown

__version__ = "0.2.0"
__all__ = [
    "Anchor", "AnchorStatus", "CheckedClaim", "Claim", "Decision", "Finding", "HoldoutInvalidated", "Policy",
    "Source", "Statement", "Status", "StructuredOutputError", "Truth", "anchor_quote", "check_claims", "decide",
    "evaluate", "extract_json", "find_amounts", "fingerprint", "flag", "freeze", "generate_structured", "lint",
    "load_frozen", "parse_amount", "parse_date_it", "render_markdown", "validate", "words_to_number",
]
