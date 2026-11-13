"""Modelli di riferimento (Baseline) deterministici e statistici per benchmark cieco.

Include:
1. Run-Rate (Media mobile a K periodi)
2. Seasonal Naive (Stesso periodo del ciclo precedente)
3. Holt Linear Exponential Smoothing (Livello + Trend smorzato)
4. Croston / SBA (Metodo standard per domanda intermittente e incassi a salti)
5. Naive Persistence (Ultimo valore noto)
"""
from __future__ import annotations

import numpy as np
import pandas as pd


class BaselineForecaster:
    """Interfaccia comune per le baseline."""
    nome: str = "Base"

    def prevedi(self, storia: np.ndarray, horizon: int, freq_ciclo: int = 12) -> dict[str, np.ndarray]:
        """Restituisce dict con 'media', 'mediana', 'q10', 'q90' di lunghezza horizon."""
        raise NotImplementedError


class NaivePersistenceForecaster(BaselineForecaster):
    """Ripete l'ultimo valore osservato costante."""
    nome = "Naive Ultimo Valore"

    def prevedi(self, storia: np.ndarray, horizon: int, freq_ciclo: int = 12) -> dict[str, np.ndarray]:
        ultimo = float(storia[-1]) if len(storia) > 0 else 0.0
        val = np.full(horizon, max(0.0, ultimo))
        # Varianza dai residui a 1 passo
        diff = np.diff(storia) if len(storia) > 1 else np.array([0.0])
        std = float(np.std(diff)) if len(diff) > 0 else 0.0
        q10 = np.maximum(0.0, val - 1.28 * std)
        q90 = val + 1.28 * std
        return {"media": val, "mediana": val, "q10": q10, "q90": q90}


class RunRateForecaster(BaselineForecaster):
    """Media mobile degli ultimi K periodi, costante sul futuro."""
    def __init__(self, k: int = 12, nome_suffisso: str = "12m"):
        self.k = k
        self.nome = f"Run-rate {nome_suffisso}"

    def prevedi(self, storia: np.ndarray, horizon: int, freq_ciclo: int = 12) -> dict[str, np.ndarray]:
        n = min(len(storia), self.k)
        if n == 0:
            media = 0.0
            std = 0.0
        else:
            finestra = storia[-n:]
            media = float(np.mean(finestra))
            std = float(np.std(finestra))
        media = max(0.0, media)
        val = np.full(horizon, media)
        q10 = np.maximum(0.0, val - 1.28 * std)
        q90 = val + 1.28 * std
        return {"media": val, "mediana": val, "q10": q10, "q90": q90}


class SeasonalNaiveForecaster(BaselineForecaster):
    """Ripete il valore dello stesso periodo nell'ultimo ciclo osservato (es. 12 mesi o 7 giorni)."""
    nome = "Stagionale Naive"

    def prevedi(self, storia: np.ndarray, horizon: int, freq_ciclo: int = 12) -> dict[str, np.ndarray]:
        L = len(storia)
        m = freq_ciclo
        if L == 0:
            val = np.zeros(horizon)
            return {"media": val, "mediana": val, "q10": val, "q90": val}
        if L < m:
            # Se la storia è più corta del ciclo, fallback su run-rate
            media = float(np.mean(storia))
            val = np.full(horizon, max(0.0, media))
            std = float(np.std(storia))
            return {"media": val, "mediana": val, "q10": np.maximum(0.0, val - 1.28 * std), "q90": val + 1.28 * std}

        val = np.empty(horizon, dtype=float)
        for i in range(horizon):
            idx = L - m + (i % m)
            val[i] = max(0.0, float(storia[idx]))

        # Residui stagionali
        if L >= 2 * m:
            res = storia[m:] - storia[:-m]
            std = float(np.std(res))
        else:
            std = float(np.std(storia))
        q10 = np.maximum(0.0, val - 1.28 * std)
        q90 = val + 1.28 * std
        return {"media": val, "mediana": val, "q10": q10, "q90": q90}


class HoltExponentialSmoothingForecaster(BaselineForecaster):
    """Holt linear exponential smoothing con trend smorzato."""
    nome = "Holt Exponential Smoothing"

    def __init__(self, alpha: float = 0.3, beta: float = 0.1, phi: float = 0.95):
        self.alpha = alpha
        self.beta = beta
        self.phi = phi  # smorzamento del trend

    def prevedi(self, storia: np.ndarray, horizon: int, freq_ciclo: int = 12) -> dict[str, np.ndarray]:
        L = len(storia)
        if L < 2:
            val = np.full(horizon, float(storia[-1]) if L == 1 else 0.0)
            return {"media": val, "mediana": val, "q10": val, "q90": val}

        # Inizializzazione
        level = float(storia[0])
        trend = float(storia[1] - storia[0])
        residui = []

        for t in range(1, L):
            y = float(storia[t])
            pred_1step = level + self.phi * trend
            residui.append(y - pred_1step)
            new_level = self.alpha * y + (1 - self.alpha) * (level + self.phi * trend)
            new_trend = self.beta * (new_level - level) + (1 - self.beta) * self.phi * trend
            level, trend = new_level, new_trend

        # Previsione ricorsiva
        val = np.empty(horizon, dtype=float)
        curr_level = level
        curr_trend = trend
        for h in range(horizon):
            curr_level = curr_level + (self.phi ** (h + 1)) * curr_trend
            val[h] = max(0.0, curr_level)

        std_res = float(np.std(residui)) if residui else float(np.std(storia))
        # L'incertezza cresce con sqrt(h)
        incertezza = 1.28 * std_res * np.sqrt(np.arange(1, horizon + 1))
        q10 = np.maximum(0.0, val - incertezza)
        q90 = val + incertezza
        return {"media": val, "mediana": val, "q10": q10, "q90": q90}


class CrostonForecaster(BaselineForecaster):
    """Metodo di Croston (con correzione SBA - Syntetos-Boylan Approximation).
    
    Standard metodologico de facto per serie temporali intermittenti (molti zeri, salti rari).
    Scinde la domanda in ampiezza del salto z_t e intervallo temporale p_t fra i salti.
    """
    def __init__(self, alpha: float = 0.15, usa_sba: bool = True):
        self.alpha = alpha
        self.usa_sba = usa_sba
        self.nome = "Croston SBA" if usa_sba else "Croston Standard"

    def prevedi(self, storia: np.ndarray, horizon: int, freq_ciclo: int = 12) -> dict[str, np.ndarray]:
        storia = np.asarray(storia, dtype=float)
        L = len(storia)
        indici_nonzeri = np.where(storia > 0)[0]

        if len(indici_nonzeri) == 0:
            val = np.zeros(horizon)
            return {"media": val, "mediana": val, "q10": val, "q90": val}

        # Ampiezza primo salto e intervallo iniziale
        z = float(storia[indici_nonzeri[0]])
        p = float(indici_nonzeri[0] + 1) if indici_nonzeri[0] > 0 else 1.0
        ultimo_nz = indici_nonzeri[0]

        for t in range(indici_nonzeri[0] + 1, L):
            if storia[t] > 0:
                intervallo = t - ultimo_nz
                z = self.alpha * storia[t] + (1 - self.alpha) * z
                p = self.alpha * intervallo + (1 - self.alpha) * p
                ultimo_nz = t

        # Tasso di flusso stimato
        if p < 1e-4:
            p = 1.0
        flusso = z / p
        if self.usa_sba:
            # Correzione Syntetos-Boylan: riduce il bias positivo di sovrastima
            flusso = flusso * (1.0 - self.alpha / 2.0)

        flusso = max(0.0, flusso)
        val = np.full(horizon, flusso)

        # Su serie intermittente, la mediana dei singoli periodi è spesso 0 se p > 2
        mediana_periodo = flusso if p < 1.5 else 0.0
        mediana_arr = np.full(horizon, mediana_periodo)

        std_nonzeri = float(np.std(storia[indici_nonzeri])) if len(indici_nonzeri) > 1 else flusso
        q10 = np.full(horizon, 0.0)
        q90 = np.full(horizon, max(flusso, flusso + 1.28 * std_nonzeri))

        return {"media": val, "mediana": mediana_arr, "q10": q10, "q90": q90}
