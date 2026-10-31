"""Frozen holdout: measure accuracy in a way you can defend in front of an auditor.

1. ``fingerprint`` the system (code, prompts, model id, thresholds).
2. ``freeze`` the evaluation sample BEFORE running the system on it; the manifest stores ids, seed, fingerprint.
3. ``load_frozen`` refuses the sample if the system changed: changing the reader means drawing a new sample,
   otherwise you are tuning on the test set.
4. ``evaluate`` counts abstentions apart from errors: coverage and selective accuracy, plus the wrong ids.

The gold answers must come from people. A gold set written by a model is not an independent reference.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Union

PathLike = Union[str, Path]


class HoldoutInvalidated(RuntimeError):
    """The system changed after the sample was frozen."""


def fingerprint(paths: Iterable[PathLike] = (), extra: Optional[Mapping[str, Any]] = None) -> str:
    """SHA-256 over file contents (sorted by path) and a JSON dump of ``extra`` (prompt, model, thresholds)."""
    h = hashlib.sha256()
    for p in sorted(Path(x) for x in paths):
        h.update(p.as_posix().encode())
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    h.update(json.dumps(extra or {}, sort_keys=True, default=str).encode())
    return h.hexdigest()


def freeze(item_ids: Iterable[str], n: int, seed: int, system_fingerprint: str, path: PathLike) -> list[str]:
    """Draw ``n`` ids with ``seed`` and write the manifest. Refuses to overwrite an existing one."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"{path} exists: a frozen sample is never redrawn in place")
    ids = sorted(set(item_ids))
    if n > len(ids):
        raise ValueError(f"asked for {n} items, only {len(ids)} available")
    sample = sorted(random.Random(seed).sample(ids, n))
    manifest = {
        "ids": sample, "seed": seed, "fingerprint": system_fingerprint, "population": len(ids),
        "frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return sample


def load_frozen(path: PathLike, system_fingerprint: str) -> list[str]:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    if manifest["fingerprint"] != system_fingerprint:
        raise HoldoutInvalidated(
            "the system changed after the sample was frozen: draw a new sample with a new seed and path"
        )
    return list(manifest["ids"])


@dataclass(frozen=True)
class Report:
    n: int
    answered: int
    correct: int
    wrong: int
    abstained: int
    coverage: float              # answered / n
    selective_accuracy: float    # correct / answered (1.0 when nothing answered is wrong)
    wrong_ids: tuple[str, ...]
    missing_ids: tuple[str, ...]  # in the sample but without a prediction: counted as abstained

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate(predictions: Mapping[str, Any], gold: Mapping[str, Any], ids: Optional[Iterable[str]] = None) -> Report:
    """``predictions[id] = None`` means the system abstained."""
    ids = sorted(ids) if ids is not None else sorted(gold)
    correct = wrong = abstained = 0
    wrong_ids, missing = [], []
    for i in ids:
        if i not in predictions:
            missing.append(i)
            abstained += 1
            continue
        p = predictions[i]
        if p is None:
            abstained += 1
        elif p == gold[i]:
            correct += 1
        else:
            wrong += 1
            wrong_ids.append(i)
    answered = correct + wrong
    n = len(ids)
    return Report(
        n=n, answered=answered, correct=correct, wrong=wrong, abstained=abstained,
        coverage=answered / n if n else 0.0,
        selective_accuracy=correct / answered if answered else 1.0,
        wrong_ids=tuple(wrong_ids), missing_ids=tuple(missing),
    )
