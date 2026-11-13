"""Le cinque baseline sugli scenari sintetici, caso per caso (python examples/backtest_synthetic.py).

Aggiungi il tuo modello alla lista (stessa interfaccia delle baseline) o Timestral:
    from zt_anchor.backtest.modello_timestral import ModelloTimestral   # pip install timestral torch
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from zt_anchor.backtest import baseline_standard, casi_sintetici, classifica, valuta  # noqa: E402

for caso in casi_sintetici():
    risultati = valuta(caso, baseline_standard(caso.freq_ciclo))
    print(f"\n== {caso.nome}  ({len(caso.tagli_ciechi)} tagli, orizzonte {caso.orizzonte_h})")
    print(classifica(risultati).round(1).to_string())
