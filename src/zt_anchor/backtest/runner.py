"""Backtest a finestra cieca: per ogni taglio il modello vede SOLO la storia fino al taglio.

Un modello è qualunque oggetto con ``nome`` e ``prevedi(storia, horizon, freq_ciclo) -> dict`` che restituisce
``media``, ``mediana``, ``q10``, ``q90`` (array lunghi ``horizon``) e, se li ha, ``quantili`` (horizon, Q).
Le baseline di ``baselines.py`` rispettano già questa interfaccia; ``modello_timestral`` adatta un foundation
model per serie storiche.

Regole che il runner fa rispettare:
- separazione causale: la storia passata al modello è tagliata qui, non dal modello;
- su serie multivariate il modello vede il target (colonna ``target`` se esiste, altrimenti la somma);
- la regola di scelta del modello va fissata PRIMA di guardare i risultati (vedi README).
"""
from __future__ import annotations

import time
from typing import Any, Iterable, Protocol

import numpy as np
import pandas as pd

from .casi import SerieCaso
from .metriche import calcola_metriche


class Modello(Protocol):
    nome: str

    def prevedi(self, storia: np.ndarray, horizon: int, freq_ciclo: int = 12) -> dict[str, np.ndarray]: ...


def _target(serie: pd.Series | pd.DataFrame) -> pd.Series:
    if isinstance(serie, pd.DataFrame):
        return serie["target"] if "target" in serie.columns else serie.sum(axis=1)
    return serie


def tagli_ciechi(caso: SerieCaso) -> Iterable[tuple[Any, np.ndarray, np.ndarray]]:
    """(taglio, storia fino al taglio incluso, effettivo dei successivi ``orizzonte_h`` passi)."""
    s = _target(caso.serie)
    for taglio in caso.tagli_ciechi:
        storia = s.loc[s.index <= taglio].to_numpy(dtype=float)
        futuro = s.loc[s.index > taglio].iloc[: caso.orizzonte_h].to_numpy(dtype=float)
        if len(futuro):
            yield taglio, storia, futuro


def valuta(caso: SerieCaso, modelli: Iterable[Modello]) -> pd.DataFrame:
    """Una riga per (taglio, modello) con le metriche di ``metriche.calcola_metriche``."""
    righe = []
    modelli = list(modelli)
    for i, (taglio, storia, eff) in enumerate(tagli_ciechi(caso), 1):
        for m in modelli:
            t0 = time.perf_counter()
            p = m.prevedi(storia.copy(), len(eff), freq_ciclo=caso.freq_ciclo)
            secondi = time.perf_counter() - t0
            met = calcola_metriche(
                eff, p["media"], pred_mediana=p.get("mediana"), q10=p.get("q10"), q90=p.get("q90"),
                qq=p.get("quantili"), ultimo_valore_storia=float(storia[-1]) if len(storia) else None,
            )
            righe.append({
                "id_caso": caso.id_caso, "taglio": str(getattr(taglio, "date", lambda: taglio)()),
                "taglio_idx": i, "modello": m.nome, "tempo_sec": round(secondi, 4), **met,
            })
    return pd.DataFrame(righe)


def classifica(risultati: pd.DataFrame, metrica: str = "punteggio") -> pd.DataFrame:
    """Media della metrica per modello su tutti i tagli e i casi (più bassa = meglio)."""
    return (risultati.groupby("modello")[metrica].agg(["mean", "median", "count"])
            .sort_values("mean").rename(columns={"mean": f"{metrica}_medio", "median": f"{metrica}_mediano",
                                                 "count": "tagli"}))
