import numpy as np
import pandas as pd

from zt_anchor.backtest import (
    RunRateForecaster,
    applica_fattore,
    baseline_standard,
    calcola_metriche,
    casi_sintetici,
    classifica,
    fattore_conforme,
    media_da_quantili,
    tagli_ciechi,
    valuta,
)
from zt_anchor.backtest.quantili import LIVELLI


def test_scenari_sintetici_riproducibili():
    a = {c.id_caso: _target_sum(c) for c in casi_sintetici()}
    b = {c.id_caso: _target_sum(c) for c in casi_sintetici()}
    assert a == b and len(a) == 5


def _target_sum(c):
    s = c.serie["target"] if isinstance(c.serie, pd.DataFrame) else c.serie
    return round(float(s.sum()), 6)


class _Spia:
    """Modello che registra la storia ricevuta."""
    nome = "spia"

    def __init__(self):
        self.viste = []

    def prevedi(self, storia, horizon, freq_ciclo=12):
        self.viste.append(storia.copy())
        z = np.zeros(horizon)
        return {"media": z, "mediana": z, "q10": z, "q90": z}


def test_il_modello_non_vede_il_futuro():
    caso = casi_sintetici()[0]
    spia = _Spia()
    valuta(caso, [spia])
    for vista, taglio in zip(spia.viste, caso.tagli_ciechi):
        assert len(vista) == int((caso.serie.index <= taglio).sum())
    # cambiare il futuro non cambia ciò che il modello vede
    alterato = caso.serie.copy()
    alterato[alterato.index > caso.tagli_ciechi[0]] *= 100
    caso.serie = alterato
    spia2 = _Spia()
    valuta(caso, [spia2])
    assert np.array_equal(spia.viste[0], spia2.viste[0])


def test_valuta_tutte_le_baseline_su_tutti_i_casi():
    righe = pd.concat([valuta(c, baseline_standard(c.freq_ciclo)) for c in casi_sintetici()])
    assert set(righe["modello"]) == {m.nome for m in baseline_standard()} | {"Run-rate 7p"}
    assert righe["wape_pct"].notna().all()
    top = classifica(righe)
    assert list(top.columns) == ["punteggio_medio", "punteggio_mediano", "tagli"]


def test_metriche_caso_perfetto():
    eff = np.array([10.0, 20.0, 30.0])
    m = calcola_metriche(eff, eff, q10=eff - 1, q90=eff + 1)
    assert m["wape_pct"] == 0 and m["scarto_cumulato_pct"] == 0 and m["copertura_80_pct"] == 100.0


def test_media_da_quantili_simmetrica_e_asimmetrica():
    qq = np.array([50.0 + 10 * (q - 0.5) for q in LIVELLI])  # quantili simmetrici attorno a 50
    assert abs(media_da_quantili(qq) - 50.0) < 1e-9
    asim = np.array([0.0 if q < 0.7 else 100.0 for q in LIVELLI])  # 70% zeri, poi salti: mediana 0
    assert asim[LIVELLI.index(0.5)] == 0 and media_da_quantili(asim) > 25


def test_fattore_conforme_stringe_una_banda_troppo_larga():
    rng = np.random.default_rng(0)
    passati = []
    for _ in range(20):
        eff = rng.normal(100, 5, 6)
        med = np.full(6, 100.0)
        passati.append((eff, med, med - 50, med + 50))  # banda enorme
    s = fattore_conforme(passati, 0.8)
    assert 0.05 < s < 0.3
    lo, hi = applica_fattore(np.full(6, 100.0), np.full(6, 50.0), np.full(6, 150.0), s)
    assert (hi - lo).mean() < 30


def test_run_rate_su_storia_breve():
    p = RunRateForecaster(k=12).prevedi(np.array([5.0, 7.0]), 3)
    assert p["media"].shape == (3,)


def test_tagli_ciechi_generatore():
    caso = casi_sintetici()[2]
    tagli = list(tagli_ciechi(caso))
    assert len(tagli) == 3 and all(len(f) <= caso.orizzonte_h for _, _, f in tagli)
