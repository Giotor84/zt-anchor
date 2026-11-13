"""Adattatore facoltativo per Timestral (foundation model zero-shot per serie storiche).

    pip install timestral torch          # pesi da Hugging Face: mistralai/Timestral-<taglia>

Restituisce media (valore atteso dai 21 quantili), mediana, q10, q90 e i quantili, troncati a >= 0
(incassi e conteggi non sono negativi).
"""
from __future__ import annotations

import numpy as np

from .quantili import LIVELLI, media_da_quantili


class ModelloTimestral:
    def __init__(self, taglia: str = "28M") -> None:
        from timestral import TimestralForecaster  # import qui: dipendenza facoltativa

        self.nome = f"Timestral-{taglia}"
        self._f = TimestralForecaster.from_pretrained(f"mistralai/Timestral-{taglia}")

    def prevedi(self, storia: np.ndarray, horizon: int, freq_ciclo: int = 12) -> dict[str, np.ndarray]:
        fc = self._f.forecast(np.asarray(storia, dtype=float)[None, None, :], prediction_length=horizon)
        qq = np.maximum(fc.quantiles[0].cpu().numpy(), 0.0)[0]  # (H, 21)
        return {
            "media": media_da_quantili(qq),
            "mediana": qq[:, LIVELLI.index(0.5)],
            "q10": qq[:, LIVELLI.index(0.1)],
            "q90": qq[:, LIVELLI.index(0.9)],
            "quantili": qq,
        }
