import pandas as pd, numpy as np
R=pd.read_csv("rondes.csv",parse_dates=["datum"]); R["voordeel"]=R.netto-R.willekeurig
NL=R[R.markt=="NL"]
# 1) uit-steekproef toets: kies aandelen op 2015-2020, toets op 2021-2026
regel=(NL.N==5)&(NL.K=="open")
a=NL[regel&(NL.periode=="2015-2020")].groupby("ticker").voordeel.mean()
gekozen=a[a>0].index.tolist()
b=NL[regel&(NL.periode=="2021-2026")]
print("gekozen op 2015-2020:",gekozen)
print("2021-2026 gekozen: voordeel %.4f netto %.4f n=%d"%(b[b.ticker.isin(gekozen)].voordeel.mean(),b[b.ticker.isin(gekozen)].netto.mean(),b.ticker.isin(gekozen).sum()))
print("2021-2026 niet gekozen: voordeel %.4f n=%d"%(b[~b.ticker.isin(gekozen)].voordeel.mean(),(~b.ticker.isin(gekozen)).sum()))

# 2) portefeuille-simulatie: €10.000, 2 posities van €5.000, NL, N=5 verkoop ex-dag opening
def sim(df, kapitaal=10000, slots=2, strip=False):
    df=df.sort_values("datum").copy()
    # koopdatum ~ datum - N handelsdagen; vrij-moment = ex-dag (verkoop bij opening)
    vrij=[pd.Timestamp("1900-01-01")]*slots; pot=kapitaal; log=[]
    for _,r in df.iterrows():
        koop=r.datum-pd.tseries.offsets.BDay(int(r.N))
        i=int(np.argmin(vrij))
        if vrij[i]<=koop:
            inzet=pot/slots
            ret=r.netto-(0.15*r.dividend_pct if strip else 0)
            pot+=inzet*ret; vrij[i]=r.datum
            log.append((r.datum.year,inzet*ret,r.ticker))
    L=pd.DataFrame(log,columns=["jaar","winst","ticker"])
    return L
iw=pd.read_csv("data/IWDA_AS.csv",parse_dates=["Date"]).set_index("Date")["Adj Close"]
iw_j=iw.groupby(iw.index.year).last().pct_change()
for strip in [False,True]:
    L=sim(NL[regel],strip=strip)
    j=L.groupby("jaar").agg(rondes=("winst","size"),winst_eur=("winst","sum"))
    j["rendement_%"]=j.winst_eur/100
    j["wereld_etf_%"]=(iw_j.reindex(j.index)*100).round(1)
    print("\nSimulatie €10.000, NL, koop 5 dagen voor, verkoop opening ex-dag", "(15% NIET terug)" if strip else "(15% verrekend)")
    print(j.round(1).to_string()); print("gemiddeld/jaar: %.0f euro, %d rondes"%(j.winst_eur.mean(), j.rondes.mean()))
