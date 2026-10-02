"""Momentum met trendfilter - gedeelde logica voor backtest en proefagent.

Elke maand (laatste handelsdag):
 1. score per ETF = gemiddelde van het totaalrendement over 1, 3, 6 en 12 maanden (of één periode)
 2. koop de TOP beste ETF's in gelijke delen
 3. trendfilter: een ETF wordt alleen gekocht als zijn score hoger is dan die van de geldmarkt (XEON);
    anders gaat dat deel naar de geldmarkt.
"""
import os
import numpy as np, pandas as pd

HIER = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("MOMENTUM_DATA", os.path.join(HIER, "data"))

REGIO = {"SXR8.DE": "VS (S&P 500)", "EQQQ.DE": "Nasdaq-100", "EXSA.DE": "Europa (Stoxx 600)",
         "EUNM.DE": "Opkomende markten", "IJPA.AS": "Japan", "4GLD.DE": "Goud", "EUNH.DE": "Euro-staatsobligaties"}
SECTOR = {"IUIT.L": "VS Technologie", "IUHC.L": "VS Gezondheidszorg", "IUFS.L": "VS Financiëel",
          "IUES.L": "VS Energie", "IUCD.L": "VS Luxe consumptie", "IUCS.L": "VS Basisconsumptie",
          "IUIS.L": "VS Industrie", "IUUS.L": "VS Nutsbedrijven", "IUMS.L": "VS Grondstoffen", "IUCM.L": "VS Communicatie"}
VEILIG = "XEON.DE"
# Gekozen opzet voor de proefagent (zie README): Amerikaanse sectoren + regio's buiten de VS + goud + obligaties
ALLES = {**SECTOR, **{k: v for k, v in REGIO.items() if k not in ("SXR8.DE", "EQQQ.DE")}}
NAMEN = {**REGIO, **SECTOR, VEILIG: "Geldmarkt (veilig)", "IWDA.AS": "Wereld-ETF (vergelijking)"}
USD = {t for t in SECTOR}  # noteren in dollars op Londen


def schoon(s):
    """Haal datafouten weg: een piek die de volgende dag weer terugvalt."""
    s = s.copy(); r = s.pct_change()
    for i in range(1, len(s) - 1):
        a, b = r.iloc[i], s.iloc[i + 1] / s.iloc[i] - 1
        if abs(a) > 0.08 and abs(b) > 0.07 and np.sign(a) != np.sign(b):
            s.iloc[i] = s.iloc[i - 1]
            r = s.pct_change()
    return s


def bestand(t):
    return os.path.join(DATA, t.replace(".", "_").replace("=", "_") + ".csv")


def laad(tickers):
    eurusd = pd.read_csv(bestand("EURUSD=X"), parse_dates=["Date"]).set_index("Date")["Close"]
    out = {}
    for t in tickers:
        s = pd.read_csv(bestand(t), parse_dates=["Date"]).set_index("Date")["Adj Close"].dropna()
        s = schoon(s[s > 0])
        if t in USD:  # omrekenen naar euro
            s = s / eurusd.reindex(s.index).ffill()
        out[t] = s
    df = pd.DataFrame(out).sort_index().ffill()
    return df


def scores(maand, regel="mix"):
    """maand = maandslotkoersen. Geeft score per maand per ETF."""
    if regel == "mix":
        return sum(maand / maand.shift(k) - 1 for k in (1, 3, 6, 12)) / 4
    return maand / maand.shift(int(regel)) - 1


def kies(score_rij, veilig_score, top=2):
    """Welke ETF's koop je deze maand? Geeft {ticker: gewicht}."""
    s = score_rij.dropna().sort_values(ascending=False)
    gewicht = {}
    for t in s.index[:top]:
        doel = t if s[t] > veilig_score else VEILIG
        gewicht[doel] = gewicht.get(doel, 0) + 1 / top
    return gewicht


def backtest(universum, regel="mix", top=2, start="2012-01-01", kapitaal=10000.0,
             kosten_pct=0.001, min_kosten=3.0, filter_aan=True):
    tick = list(universum) + [VEILIG]
    dag = laad(tick)
    maand = dag.resample("ME").last()
    sc = scores(maand[list(universum)], regel)
    vsc = scores(maand[[VEILIG]], regel)[VEILIG]
    maanden = maand.index[maand.index >= pd.Timestamp(start)]
    waarde, posities, rij = kapitaal, {}, []
    for i, m in enumerate(maanden[:-1]):
        # nieuw gewicht bepalen
        ok = sc.loc[m].dropna()
        ok = ok[maand.loc[m, ok.index].notna()]
        if len(ok) < top:
            continue
        w = kies(ok, vsc.loc[m] if filter_aan else -9, top)
        # kosten van herschikken
        oud = {t: v / waarde for t, v in posities.items()} if posities else {}
        omzet = sum(abs(w.get(t, 0) - oud.get(t, 0)) for t in set(w) | set(oud))
        n_orders = sum(1 for t in set(w) | set(oud) if abs(w.get(t, 0) - oud.get(t, 0)) > 1e-9)
        kosten = max(omzet * waarde * kosten_pct, n_orders * min_kosten) if n_orders else 0
        waarde -= kosten
        # rendement volgende maand
        volgende = maanden[i + 1]
        ret = sum(g * (maand.loc[volgende, t] / maand.loc[m, t] - 1) for t, g in w.items())
        posities = {t: g * waarde * (1 + maand.loc[volgende, t] / maand.loc[m, t] - 1) for t, g in w.items()}
        waarde *= 1 + ret
        rij.append(dict(maand=volgende, waarde=waarde, kosten=kosten, posities=",".join(sorted(w))))
    return pd.DataFrame(rij).set_index("maand"), maand


def kerncijfers(reeks, start_waarde=10000.0):
    r = reeks.pct_change().fillna(reeks.iloc[0] / start_waarde - 1)
    jaren = len(r) / 12
    cagr = (reeks.iloc[-1] / start_waarde) ** (1 / jaren) - 1
    piek = reeks.cummax(); dd = (reeks / piek - 1).min()
    vol = r.std() * np.sqrt(12)
    return dict(eind=round(reeks.iloc[-1]), per_jaar=round(cagr * 100, 1), grootste_daling=round(dd * 100, 1),
                beweeglijkheid=round(vol * 100, 1), sharpe=round(cagr / vol, 2) if vol else None)
