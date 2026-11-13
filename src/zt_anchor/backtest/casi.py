"""Scenari sintetici per il backtest cieco: serie con comportamento noto, per vedere dove un modello sbaglia.

- contact center giornaliero con stagionalità settimanale e rumore AR(1);
- incassi "a salti" (Poisson + Gamma, molti mesi a zero), tipici di recupero crediti e aste;
- stress: rottura di regime (-60%), outlier isolato 13x, multivariata con una variata spuria.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

@dataclass
class SerieCaso:
    id_caso: str
    nome: str
    frangia: str               # famiglia di scenario, es. "NPL_INCASSI" | "CALL_ANALYTICS" | "STRESS_TEST"
    tipo_dato: str             # "reale" | "sintetico"
    descrizione: str
    freq: str                  # "M" | "W" | "D"
    freq_ciclo: int            # 12 per mensile, 7 per giornaliero, 52 per settimanale
    serie: pd.Series | pd.DataFrame
    tagli_ciechi: list[pd.Timestamp | int]  # indici o date in cui effettuare il taglio cieco
    orizzonte_h: int           # passi futuri da prevedere per ogni taglio
    unita_misura: str          # "EUR" | "conteggio"



# --- REGIMI SINTETICI CONTROLLATI PER STRESS TEST & BOUNDARY TESTING ---

def _genera_sintetico_phone_contact_center(n_giorni: int = 180, seed: int = 42) -> SerieCaso:
    """Simula 6 mesi di contact center con stagionalità settimanale forte e rumore AR(1)."""
    rng = np.random.default_rng(seed)
    date = pd.date_range("2026-01-01", periods=n_giorni, freq="D")
    giorno_sett = date.day_of_week  # 0=Mon .. 6=Sun
    # Profilo settimanale: Lunedi picco, decresce fino a Ven, Sabato 15%, Domenica 0
    profilo = np.array([450, 420, 390, 380, 350, 60, 0])
    base = profilo[giorno_sett]
    # Rumore autoregressivo
    rumore = np.zeros(n_giorni)
    for t in range(1, n_giorni):
        rumore[t] = 0.6 * rumore[t - 1] + rng.normal(0, 35)
    serie_val = np.maximum(0.0, base + rumore)
    # Azzeramento esatto della domenica
    serie_val[giorno_sett == 6] = 0.0
    s = pd.Series(serie_val, index=date)
    tagli = [date[60], date[90], date[120], date[150]]
    return SerieCaso(
        id_caso="sintetico_contact_center_180d",
        nome="Contact Center Sintetico - Serie Continua Stagionale",
        frangia="CALL_ANALYTICS",
        tipo_dato="sintetico",
        descrizione="180 giorni di chiamate giornaliere con profilo settimanale noto, weekend e rumore AR(1).",
        freq="D",
        freq_ciclo=7,
        serie=s,
        tagli_ciechi=tagli,
        orizzonte_h=14,
        unita_misura="conteggio"
    )


def _genera_sintetico_npl_lumpy(n_mesi: int = 48, seed: int = 123) -> SerieCaso:
    """Simula 4 anni di incassi NPL ad alta intermittenza (Poisson + Gamma)."""
    rng = np.random.default_rng(seed)
    date = pd.date_range("2022-01-01", periods=n_mesi, freq="MS")
    # Tasso di arrivo transazioni per mese (Poisson media lambda=1.2)
    eventi = rng.poisson(lam=1.2, size=n_mesi)
    valori = np.zeros(n_mesi)
    for t, n in enumerate(eventi):
        if n > 0:
            # Salti distribuiti come Gamma (pochi piccoli, rari molto grandi)
            salti = rng.gamma(shape=1.5, scale=80000, size=n)
            valori[t] = salti.sum()
        else:
            valori[t] = 0.0
    s = pd.Series(valori, index=date)
    tagli = [date[24], date[30], date[36], date[40]]
    return SerieCaso(
        id_caso="sintetico_npl_lumpy_48m",
        nome="NPL Sintetico Lumpy - 4 Anni a Salti e Zeri",
        frangia="NPL_INCASSI",
        tipo_dato="sintetico",
        descrizione="48 mesi con arrivi di Poisson e importi Gamma; 30% di mesi a zero (intermittenza pura).",
        freq="M",
        freq_ciclo=12,
        serie=s,
        tagli_ciechi=tagli,
        orizzonte_h=6,
        unita_misura="EUR"
    )


def _genera_stress_regime_break(n_mesi: int = 36, seed: int = 7) -> SerieCaso:
    """Stress test: cambio strutturale improvviso (Shock / Salto di livello).
    
    Mesi 1..24: media 100k con rumore.
    Mese 25 in poi: crollo del 60% a 40k (es. moratoria, blocco normativo).
    Taglio cieco esattamente a cavallo (mesi 20, 24, 27).
    """
    rng = np.random.default_rng(seed)
    date = pd.date_range("2023-01-01", periods=n_mesi, freq="MS")
    valori = np.zeros(n_mesi)
    for t in range(n_mesi):
        if t < 24:
            valori[t] = max(0.0, 100000 + rng.normal(0, 12000))
        else:
            valori[t] = max(0.0, 40000 + rng.normal(0, 8000))
    s = pd.Series(valori, index=date)
    tagli = [date[20], date[24], date[27]]
    return SerieCaso(
        id_caso="stress_regime_break",
        nome="Stress Test - Regime Break (-60% Shock Improvviso)",
        frangia="STRESS_TEST",
        tipo_dato="sintetico",
        descrizione="Crollo improvviso del livello da 100k€ a 40k€ al mese 25. Valuta la capacità di adattamento.",
        freq="M",
        freq_ciclo=12,
        serie=s,
        tagli_ciechi=tagli,
        orizzonte_h=6,
        unita_misura="EUR"
    )


def _genera_stress_black_swan_outlier(n_mesi: int = 36, seed: int = 99) -> SerieCaso:
    """Stress test: Outlier mostruoso (Cigno Nero / Incasso record 10x).
    
    Mesi standard: media 50k.
    Mese 18: incasso eccezionale di 650k (mega aggiudicazione).
    Tagli ciechi a mese 19 (subito dopo l'outlier) e mese 24.
    """
    rng = np.random.default_rng(seed)
    date = pd.date_range("2023-01-01", periods=n_mesi, freq="MS")
    valori = np.zeros(n_mesi)
    for t in range(n_mesi):
        valori[t] = max(0.0, 50000 + rng.normal(0, 6000))
    valori[17] = 650000.0  # Mese 18 picco enorme
    s = pd.Series(valori, index=date)
    tagli = [date[18], date[22], date[26]]
    return SerieCaso(
        id_caso="stress_black_swan",
        nome="Stress Test - Black Swan Outlier (13x Spike Isolato)",
        frangia="STRESS_TEST",
        tipo_dato="sintetico",
        descrizione="Singolo incasso anomalo di 650k€ su un trend stabile di 50k€. Valuta se il modello allucina trend al rialzo.",
        freq="M",
        freq_ciclo=12,
        serie=s,
        tagli_ciechi=tagli,
        orizzonte_h=6,
        unita_misura="EUR"
    )


def _genera_stress_multivariata_spurious(n_mesi: int = 36, seed: int = 42) -> SerieCaso:
    """Stress test: Multivariata con Driver Reale + Rumore Scorrelato.
    
    Target: serie da prevedere.
    Driver 1: serie fortemente correlata.
    Driver 2: puro rumore bianco non correlato.
    """
    rng = np.random.default_rng(seed)
    date = pd.date_range("2023-01-01", periods=n_mesi, freq="MS")
    trend = np.linspace(50, 120, n_mesi)
    target = np.maximum(0.0, trend + rng.normal(0, 8, n_mesi))
    driver_vero = np.maximum(0.0, 0.8 * trend + rng.normal(0, 5, n_mesi))
    driver_spurious = rng.normal(200, 50, n_mesi)  # Rumore bianco
    df = pd.DataFrame({
        "target": target,
        "driver_correlato": driver_vero,
        "rumore_spurious": driver_spurious
    }, index=date)
    tagli = [date[20], date[26]]
    return SerieCaso(
        id_caso="stress_multivariata_spurious",
        nome="Stress Test - Multivariata con Rumore Spurio",
        frangia="STRESS_TEST",
        tipo_dato="sintetico",
        descrizione="Verifica se la presenza di variate spurie non correlate disturba la previsione del target.",
        freq="M",
        freq_ciclo=12,
        serie=df,
        tagli_ciechi=tagli,
        orizzonte_h=6,
        unita_misura="EUR"
    )


def casi_sintetici() -> list[SerieCaso]:
    """Tutti gli scenari sintetici, con tagli ciechi e orizzonti già definiti."""
    return [
        _genera_sintetico_npl_lumpy(),
        _genera_sintetico_phone_contact_center(),
        _genera_stress_regime_break(),
        _genera_stress_black_swan_outlier(),
        _genera_stress_multivariata_spurious(),
    ]
