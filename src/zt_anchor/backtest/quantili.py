"""Valore atteso dai quantili e calibrazione conforme delle bande.

- La previsione puntuale da usare è il **valore atteso** (media), non la mediana: su serie a salti (incassi,
  aste) la mediana sta sistematicamente sotto il totale reale.
- Sommare i quantili di più variate dà bande prudenziali (dipendenza perfetta), di solito troppo larghe.
  ``fattore_conforme`` misura sui tagli passati di quanto allargare o stringere la banda per avere davvero la
  copertura nominale.
"""
from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np

LIVELLI = (0.01, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5,
           0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99)


def media_da_quantili(qq: np.ndarray, livelli: Sequence[float] = LIVELLI) -> np.ndarray:
    """Valore atteso integrando la funzione quantile (trapezi) su array (..., Q)."""
    u = np.asarray(livelli, dtype=float)
    larg = np.diff(u)
    interno = ((qq[..., 1:] + qq[..., :-1]) / 2.0 * larg).sum(axis=-1)
    return interno + qq[..., 0] * u[0] + qq[..., -1] * (1.0 - u[-1])


def fattore_conforme(
    passati: Iterable[tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]],
    copertura: float = 0.80,
) -> float:
    """Moltiplicatore delle semi-ampiezze attorno alla mediana che dà la copertura voluta sui tagli passati.

    ``passati``: tuple (effettivo, mediana, q_basso, q_alto) di tagli ciechi GIÀ chiusi.
    Restituisce s tale che [med - s*(med - q_basso), med + s*(q_alto - med)] contiene la quota ``copertura``
    dei valori effettivi. s < 1: la banda era troppo larga; s > 1: troppo stretta.
    """
    punteggi = []
    for eff, med, lo, hi in passati:
        eff, med, lo, hi = (np.asarray(x, dtype=float) for x in (eff, med, lo, hi))
        sotto = np.where(eff < med, (med - eff) / np.maximum(med - lo, 1e-9), 0.0)
        sopra = np.where(eff >= med, (eff - med) / np.maximum(hi - med, 1e-9), 0.0)
        punteggi.append(np.maximum(sotto, sopra))
    if not punteggi:
        raise ValueError("servono tagli passati per calibrare")
    s = np.concatenate(punteggi)
    n = len(s)
    rango = min(n, int(np.ceil((n + 1) * copertura)))  # quantile conforme con correzione per campioni finiti
    return float(np.sort(s)[rango - 1])


def applica_fattore(med: np.ndarray, lo: np.ndarray, hi: np.ndarray, s: float) -> tuple[np.ndarray, np.ndarray]:
    med, lo, hi = (np.asarray(x, dtype=float) for x in (med, lo, hi))
    return np.maximum(0.0, med - s * (med - lo)), med + s * (hi - med)
