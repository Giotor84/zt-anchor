"""Metriche di valutazione per backtest e benchmark alla cieca.

Implementazione trasparente in NumPy/Pandas senza dipendenze esterne.
Supporta previsioni puntuali (media, mediana) e probabilistiche (quantili 21 livelli, bande, pinball loss).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LIVELLI_QUANTILI = (
    0.01, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5,
    0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99
)


def pinball_loss_totale(eff: np.ndarray, qq: np.ndarray, livelli: tuple[float, ...] = LIVELLI_QUANTILI) -> float:
    """Calcola la Pinball Loss media (approssimazione del CRPS) sui 21 quantili.
    
    eff: shape (H,)
    qq: shape (H, Q) dove Q = len(livelli)
    """
    if qq.ndim == 1:
        return float(np.nan)
    loss = 0.0
    for j, q in enumerate(livelli):
        diff = eff - qq[:, j]
        loss += np.maximum(q * diff, (q - 1.0) * diff).mean()
    return float(loss / len(livelli))


def calcola_metriche(eff: np.ndarray,
                     pred_media: np.ndarray,
                     pred_mediana: np.ndarray | None = None,
                     q10: np.ndarray | None = None,
                     q90: np.ndarray | None = None,
                     qq: np.ndarray | None = None,
                     ultimo_valore_storia: float | None = None) -> dict:
    """Calcola set esaustivo di metriche cieche su orizzonte H."""
    eff = np.asarray(eff, dtype=float)
    p = np.asarray(pred_media, dtype=float)
    h = len(eff)
    if h == 0:
        return {}

    tot_eff = float(eff.sum())
    tot_p = float(p.sum())
    denom_wape = tot_eff if tot_eff > 1e-6 else 1e-6

    # Errore cumulato sul totale della finestra
    scarto_cumulato_pct = 100.0 * (tot_p - tot_eff) / denom_wape
    wape_pct = 100.0 * np.abs(p - eff).sum() / denom_wape
    mae = float(np.abs(p - eff).mean())
    rmse = float(np.sqrt(np.mean((p - eff) ** 2)))

    # Mediana (se fornita)
    if pred_mediana is not None:
        med = np.asarray(pred_mediana, dtype=float)
        tot_med = float(med.sum())
        scarto_mediana_pct = 100.0 * (tot_med - tot_eff) / denom_wape
        wape_mediana_pct = 100.0 * np.abs(med - eff).sum() / denom_wape
    else:
        scarto_mediana_pct = float(scarto_cumulato_pct)
        wape_mediana_pct = float(wape_pct)

    # Copertura intervallo P10-P90 (nominale 80%) e sharpness (larghezza relativa)
    if q10 is not None and q90 is not None:
        q10_arr = np.asarray(q10, dtype=float)
        q90_arr = np.asarray(q90, dtype=float)
        in_banda = (eff >= q10_arr) & (eff <= q90_arr)
        copertura_80_pct = float(100.0 * np.mean(in_banda))
        larghezza_media = float((q90_arr - q10_arr).mean())
        media_eff = float(eff.mean()) if eff.mean() > 1e-6 else 1.0
        sharpness_pct = float(100.0 * larghezza_media / media_eff)
        cumulato_in_banda = bool(q10_arr.sum() <= tot_eff <= q90_arr.sum())
    else:
        copertura_80_pct = float(np.nan)
        sharpness_pct = float(np.nan)
        cumulato_in_banda = False

    # Pinball / CRPS
    if qq is not None:
        pinball = pinball_loss_totale(eff, qq)
    else:
        pinball = float(np.nan)

    # Accuratezza direzionale (se abbiamo l'ultimo valore storico o almeno 2 passi)
    if ultimo_valore_storia is not None and h >= 1:
        serie_eff = np.concatenate(([ultimo_valore_storia], eff))
        serie_p = np.concatenate(([ultimo_valore_storia], p))
        diff_eff = np.diff(serie_eff)
        diff_p = np.diff(serie_p)
        concordi = (np.sign(diff_eff) == np.sign(diff_p)) | (np.abs(diff_eff) < 1e-6)
        dir_acc_pct = float(100.0 * np.mean(concordi))
    elif h >= 2:
        diff_eff = np.diff(eff)
        diff_p = np.diff(p)
        concordi = (np.sign(diff_eff) == np.sign(diff_p)) | (np.abs(diff_eff) < 1e-6)
        dir_acc_pct = float(100.0 * np.mean(concordi))
    else:
        dir_acc_pct = float(np.nan)

    # Punteggio sintetico composito: (|scarto| + WAPE) / 2
    punteggio = (abs(scarto_cumulato_pct) + wape_pct) / 2.0

    return {
        "orizzonte_h": h,
        "totale_effettivo": round(tot_eff, 2),
        "totale_previsto": round(tot_p, 2),
        "scarto_cumulato_pct": round(scarto_cumulato_pct, 2),
        "scarto_mediana_pct": round(scarto_mediana_pct, 2),
        "wape_pct": round(wape_pct, 2),
        "wape_mediana_pct": round(wape_mediana_pct, 2),
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "copertura_80_pct": round(copertura_80_pct, 1) if not np.isnan(copertura_80_pct) else None,
        "sharpness_pct": round(sharpness_pct, 1) if not np.isnan(sharpness_pct) else None,
        "cumulato_in_banda": cumulato_in_banda,
        "pinball_loss": round(pinball, 2) if not np.isnan(pinball) else None,
        "directional_accuracy_pct": round(dir_acc_pct, 1) if not np.isnan(dir_acc_pct) else None,
        "punteggio": round(punteggio, 2),
    }
