"""zt-backtest: valutare previsioni di serie storiche senza imbrogliare (finestra cieca, baseline, bande calibrate)."""
from .baselines import (
    CrostonForecaster,
    HoltExponentialSmoothingForecaster,
    NaivePersistenceForecaster,
    RunRateForecaster,
    SeasonalNaiveForecaster,
)
from .casi import SerieCaso, casi_sintetici
from .metriche import calcola_metriche, pinball_loss_totale
from .quantili import applica_fattore, fattore_conforme, media_da_quantili
from .runner import classifica, tagli_ciechi, valuta

__version__ = "0.1.0"


def baseline_standard(freq_ciclo: int = 12) -> list:
    """Le cinque baseline da battere prima di credere a un modello più complesso."""
    k = min(12, freq_ciclo)
    return [
        NaivePersistenceForecaster(),
        RunRateForecaster(k=k, nome_suffisso=f"{k}p"),
        SeasonalNaiveForecaster(),
        HoltExponentialSmoothingForecaster(),
        CrostonForecaster(usa_sba=True),
    ]


__all__ = [
    "CrostonForecaster", "HoltExponentialSmoothingForecaster", "NaivePersistenceForecaster", "RunRateForecaster",
    "SeasonalNaiveForecaster", "SerieCaso", "applica_fattore", "baseline_standard", "calcola_metriche",
    "casi_sintetici", "classifica", "fattore_conforme", "media_da_quantili", "pinball_loss_totale",
    "tagli_ciechi", "valuta",
]
