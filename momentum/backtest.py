import pandas as pd
from strategie import *
pd.set_option("display.width", 200)
def bench(maand, t, start):
    s = maand[t][maand.index >= pd.Timestamp(start)]
    return 10000 * s / s.iloc[0]
rows = []
for naam, uni, start in [("Regio", REGIO, "2012-01-01"), ("Sector", SECTOR, "2018-10-01")]:
    for regel in ["mix", "3", "6", "12"]:
        for top in [1, 2, 3]:
            for filt in [True, False]:
                res, maand = backtest(uni, regel, top, start, filter_aan=filt)
                k = kerncijfers(res.waarde)
                rows.append(dict(universum=naam, regel=regel, top=top, filter=filt, start=res.index[0].date(),
                                 trades=(res.posities != res.posities.shift()).sum(), kosten=round(res.kosten.sum()), **k))
    # vergelijking: wereld-ETF kopen en vasthouden over dezelfde maanden
    m = laad(["IWDA.AS"]).resample("ME").last()
    w = bench(m, "IWDA.AS", res.index[0] - pd.offsets.MonthEnd(1)).loc[res.index[0]:]
    rows.append(dict(universum=naam, regel="WERELD-ETF", start=w.index[0].date(), **kerncijfers(w.iloc[1:], w.iloc[0])))
R = pd.DataFrame(rows)
R.to_csv("uitkomst_grid.csv", index=False)
print(R.to_string())
