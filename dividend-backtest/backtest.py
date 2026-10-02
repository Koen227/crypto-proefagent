"""Backtest dividend capture.
Koop op slotkoers N handelsdagen voor de ex-dividenddag, verkoop op dag K na ex-dag
(K=0 = slotkoers van de ex-dag, 'open' = openingskoers ex-dag).
Netto = koersresultaat + dividend - verloren bronbelasting - kosten."""
import os, glob, json
import pandas as pd, numpy as np

D = os.path.join(os.path.dirname(__file__), "data")
US = {"KO","PEP","PG","JNJ","MCD","CL","KMB","WMT","DUK","SO","ED","VZ"}
KOSTEN = {"NL": 0.0018, "US": 0.0016}     # heen+terug: commissie IBKR + spread (+valuta VS)
VERLOREN_BELASTING = {"NL": 0.0, "US": 0.15}  # NL verrekenbaar; VS 15% kwijt onder box 3-vrijstelling
NS = [1, 2, 3, 5, 10]
KS = ["open", 0, 1, 2, 3, 5, 10]
SPLITS = pd.Timestamp("2021-01-01")

def laad(t):
    df = pd.read_csv(os.path.join(D, t + ".csv"), parse_dates=["Date"]).set_index("Date")
    return df[df["Close"] > 0]

def rondes(t):
    df = laad(t); markt = "US" if t in US else "NL"
    c, o, adj, div = df["Close"].values, df["Open"].values, df["Adj Close"].values, df["Dividends"].values
    ex_idx = np.where(div > 0)[0]
    rij = []
    for i in ex_idx:
        d = div[i]
        if i < 1: continue
        drop = (c[i-1] - o[i]) / d if o[i] > 0 else np.nan
        for N in NS:
            if i - N < 0: continue
            pb = c[i-N]
            for K in KS:
                if K == "open":
                    ps, L = o[i], N
                    if ps <= 0: continue
                else:
                    if i + K >= len(c): continue
                    ps, L = c[i+K], N + K
                bruto = (ps - pb + d) / pb
                netto = (ps - pb + d * (1 - VERLOREN_BELASTING[markt])) / pb - KOSTEN[markt]
                rij.append(dict(ticker=t, markt=markt, datum=df.index[i], N=N, K=str(K), L=L,
                                dividend_pct=d / pb, koers_pct=(ps - pb) / pb, bruto=bruto, netto=netto, daling_ratio=drop))
    return rij, df

def basis(df, L):
    """Gemiddeld totaalrendement (incl. dividend) van ELK willekeurig venster van L dagen."""
    a = df["Adj Close"].values
    return np.mean(a[L:] / a[:-L] - 1)

alle, dfs = [], {}
for f in sorted(glob.glob(os.path.join(D, "*.csv"))):
    t = os.path.basename(f)[:-4]
    if t == "IWDA_AS": continue
    r, df = rondes(t); alle += r; dfs[t] = df
R = pd.DataFrame(alle)
R["periode"] = np.where(R["datum"] < SPLITS, "2015-2020", "2021-2026")
# willekeurig-moment vergelijking
bas = {(t, L): basis(dfs[t], L) for t in dfs for L in R["L"].unique()}
R["willekeurig"] = [bas[(t, L)] for t, L in zip(R["ticker"], R["L"])]
R["extra_vs_willekeurig"] = R["bruto"] - R["willekeurig"]
R.to_csv(os.path.join(os.path.dirname(__file__), "rondes.csv"), index=False)

def stats(g):
    return pd.Series(dict(rondes=len(g), netto_gem=g.netto.mean(), netto_mediaan=g.netto.median(),
                          winst_kans=(g.netto > 0).mean(), slechtste=g.netto.min(),
                          extra_vs_willekeurig=g.extra_vs_willekeurig.mean(), daling_ratio=g.daling_ratio.median()))

out = {}
out["per_regel"] = R.groupby(["N","K"]).apply(stats).sort_values("netto_gem", ascending=False)
out["per_regel_markt"] = R.groupby(["markt","N","K"]).apply(stats)
out["per_regel_periode"] = R.groupby(["periode","N","K"]).apply(stats)
pd.set_option("display.width", 200); pd.set_option("display.max_rows", 500)
for k, v in out.items():
    v.to_csv(os.path.join(os.path.dirname(__file__), f"uitkomst_{k}.csv"))
print(out["per_regel"].round(4))
