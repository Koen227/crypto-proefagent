import pandas as pd
from strategie import *
UIT = {t: n for t, (n, p) in UITBREIDING.items()}
REGIO_PLUS = {**REGIO, **UIT}
ALLES_PLUS = {**ALLES, **UIT}
w = laad(["IWDA.AS"]).resample("ME").last()["IWDA.AS"]
rows = []
def wereld(res):
    s = w.loc[res.index[0] - pd.offsets.MonthEnd(1):res.index[-1]]
    return kerncijfers(s.iloc[1:], s.iloc[0])
for naam, uni, start in [("Huidig (16)", ALLES, "2018-10-01"), ("Uitgebreid (28)", ALLES_PLUS, "2018-10-01"),
                         ("Regio's (7)", REGIO, "2013-03-01"), ("Regio's + uitbreiding (19)", REGIO_PLUS, "2013-03-01")]:
    for top in [3, 4, 5]:
        res, _ = backtest(uni, "mix", top, start)
        r1 = res[res.index < "2021-01-01"].waarde; r2 = res[res.index >= "2021-01-01"].waarde
        rows.append(dict(lijst=naam, top=top, vanaf=res.index[0].date(), **kerncijfers(res.waarde),
                         tot_2020=round(((r1.iloc[-1]/10000)**(12/len(r1))-1)*100,1),
                         vanaf_2021=round(((r2.iloc[-1]/r1.iloc[-1])**(12/len(r2))-1)*100,1)))
    rows.append(dict(lijst=naam, top="WERELD-ETF", vanaf=res.index[0].date(), **wereld(res)))
R = pd.DataFrame(rows); R.to_csv("uitkomst_uitbreiding.csv", index=False); print(R.to_string())
res, _ = backtest(ALLES_PLUS, "mix", 4, "2018-10-01")
print(res.posities.str.split(",").explode().value_counts().rename(lambda t: NAMEN.get(t, t)).head(15))
