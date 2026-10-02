"""Welke ETF's zijn 'goed te volgen' met momentum? Per ETF: trendregel (vasthouden als score > geldmarkt, anders geldmarkt)
tegen gewoon vasthouden. Bepaald op data t/m 2020, getoetst op 2021-2026."""
import numpy as np, pandas as pd
from strategie import *
UIT = {t: n for t, (n, p) in UITBREIDING.items()}
KAND = {**ALLES, **UIT, "SXR8.DE": "", "EQQQ.DE": ""}
dag = laad(list(KAND) + [VEILIG]); m = dag.resample("ME").last()
sc = scores(m, "mix"); ret = m.pct_change().shift(-1)  # rendement volgende maand
rows = []
for t in KAND:
    aan = sc[t] > sc[VEILIG]
    trend = np.where(aan, ret[t], ret[VEILIG]) - 0.001 * aan.astype(int).diff().abs().fillna(0)
    df = pd.DataFrame({"trend": trend, "hold": ret[t]}, index=m.index).dropna()
    df = df[df.index >= df.index[0] + pd.DateOffset(months=12)]
    def stat(d):
        if len(d) < 24: return np.nan, np.nan
        sh = lambda x: x.mean() / x.std() * np.sqrt(12)
        return (sh(d.trend) - sh(d.hold)), (d.trend.mean() - d.hold.mean()) * 12 * 100
    a = stat(df[df.index < "2021-01-01"]); b = stat(df[df.index >= "2021-01-01"])
    rows.append(dict(ticker=t, naam=NAMEN.get(t, t), start=df.index[0].date(), voor_sharpe_plus=a[0], na_sharpe_plus=b[0], voor_rend_plus=a[1], na_rend_plus=b[1]))
R = pd.DataFrame(rows).set_index("ticker").sort_values("voor_sharpe_plus", ascending=False)
pd.set_option("display.width", 200); print(R.round(2).to_string())
ok = R.dropna()
print("\nSamenhang voor/na (rangcorrelatie):", round(ok.voor_sharpe_plus.corr(ok.na_sharpe_plus, method="spearman"), 2), "n =", len(ok))
R.to_csv("uitkomst_selectie.csv")
