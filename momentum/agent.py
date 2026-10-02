#!/usr/bin/env python3
"""Momentum Proefagent - papieren handel met fictief geld (€10.000).

Draait elke werkdag na sluiting van de Europese beurzen (via GitHub):
 - haalt de slotkoersen op (Yahoo Finance, openbaar, geen account nodig);
 - waardeert de fictieve posities in euro's;
 - één keer per maand (eerste run in een nieuwe maand): scores berekenen op de slotkoersen
   van de vorige maand en herverdelen over de 3 sterkste ETF's (trendfilter: zwakker dan
   de geldmarkt -> dat deel naar de geldmarkt);
 - houdt een vergelijking bij: hetzelfde bedrag in de wereld-ETF (IWDA) kopen en vasthouden.

Er wordt nergens echt gehandeld.
"""
import datetime as dt, json, os, sys, tempfile, time

import pandas as pd
import yfinance as yf

HIER = os.path.dirname(os.path.abspath(__file__))
TMP = tempfile.mkdtemp()
os.environ["MOMENTUM_DATA"] = TMP
sys.path.insert(0, HIER)
import strategie as S  # noqa: E402

STATE = os.path.join(HIER, "state.json")
STAND = os.path.join(HIER, "..", "docs", "momentum.json")
START_KAPITAAL = 10000.0
TOP = 3
REGEL = "mix"
KOSTEN_PCT = 0.001       # commissie + bied-laatverschil (Interactive Brokers)
MIN_KOSTEN = 3.0         # minimum per order
MIN_AANPASSING = 0.05    # bestaande positie alleen bijstellen bij >5% afwijking (scheelt kosten)
BENCH = "IWDA.AS"


def ophalen():
    tickers = list(S.ALLES) + [S.VEILIG, BENCH, "EURUSD=X"]
    for t in tickers:
        for poging in range(3):
            try:
                df = yf.Ticker(t).history(period="3y", auto_adjust=False)
                if df.empty:
                    raise RuntimeError("leeg")
                df = df[["Close", "Adj Close"]]
                df.index = df.index.tz_localize(None).date
                df.index.name = "Date"
                df.to_csv(S.bestand(t))
                break
            except Exception as e:
                print(t, "poging", poging + 1, "mislukt:", e)
                time.sleep(5)
        else:
            raise SystemExit(f"Geen koersen voor {t}; deze run wordt overgeslagen.")
        time.sleep(0.5)
    return S.laad(list(S.ALLES) + [S.VEILIG, BENCH])


def laad_state():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return dict(start=None, kas=START_KAPITAAL, posities={}, maand=None, historie=[],
                transacties=[], bench_eenheden=None, kosten_totaal=0.0)


def main():
    st = laad_state()
    dag = ophalen()
    laatste = dag.index[-1]
    prijs = dag.loc[laatste]
    vandaag = laatste.date().isoformat()

    if st["start"] is None:
        st["start"] = vandaag
        st["bench_eenheden"] = START_KAPITAAL / prijs[BENCH]

    def waarde():
        return st["kas"] + sum(n * prijs[t] for t, n in st["posities"].items())

    maand_nu = laatste.strftime("%Y-%m")
    signaal = None
    if st["maand"] != maand_nu:
        # scores op de laatste slotkoers van de vorige maand
        maandreeks = dag[dag.index < pd.Timestamp(laatste.year, laatste.month, 1)].resample("ME").last()
        sc = S.scores(maandreeks[list(S.ALLES)], REGEL).iloc[-1].dropna()
        vsc = S.scores(maandreeks[[S.VEILIG]], REGEL)[S.VEILIG].iloc[-1]
        doel = S.kies(sc, vsc, TOP)
        totaal = waarde()
        orders = []
        for t in sorted(set(doel) | set(st["posities"])):
            huidig = st["posities"].get(t, 0) * prijs[t]
            gewenst = doel.get(t, 0) * totaal * 0.995  # kleine buffer voor kosten
            verschil = gewenst - huidig
            nieuw_of_weg = (huidig == 0) != (gewenst == 0)
            if abs(verschil) < 1 or (not nieuw_of_weg and abs(verschil) < MIN_AANPASSING * totaal):
                continue
            orders.append((t, verschil))
        # eerst verkopen, dan kopen
        for t, verschil in sorted(orders, key=lambda x: x[1]):
            kosten = max(abs(verschil) * KOSTEN_PCT, MIN_KOSTEN)
            st["posities"][t] = st["posities"].get(t, 0) + verschil / prijs[t]
            if abs(st["posities"][t] * prijs[t]) < 1:
                st["posities"].pop(t)
            st["kas"] -= verschil + kosten
            st["kosten_totaal"] += kosten
            st["transacties"].append(dict(datum=vandaag, ticker=t, naam=S.NAMEN.get(t, t),
                                          actie="koop" if verschil > 0 else "verkoop",
                                          bedrag=round(abs(verschil), 2), koers=round(float(prijs[t]), 4),
                                          kosten=round(kosten, 2)))
        st["maand"] = maand_nu
        signaal = dict(datum=vandaag, scores={t: round(float(v) * 100, 2) for t, v in sc.sort_values(ascending=False).items()},
                       geldmarkt=round(float(vsc) * 100, 2), gekozen=doel)
        st["laatste_signaal"] = signaal

    w = waarde()
    b = st["bench_eenheden"] * prijs[BENCH]
    if st["historie"] and st["historie"][-1]["datum"] == vandaag:
        st["historie"].pop()
    st["historie"].append(dict(datum=vandaag, waarde=round(w, 2), wereld=round(b, 2)))

    json.dump(st, open(STATE, "w"), indent=1)
    stand = dict(
        bijgewerkt=dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"), koersdatum=vandaag, start=st["start"],
        start_kapitaal=START_KAPITAAL, waarde=round(w, 2), wereld=round(b, 2), kas=round(st["kas"], 2),
        kosten_totaal=round(st["kosten_totaal"], 2),
        posities=[dict(ticker=t, naam=S.NAMEN.get(t, t), waarde=round(n * prijs[t], 2), aandeel=round(n * prijs[t] / w * 100, 1))
                  for t, n in sorted(st["posities"].items(), key=lambda x: -x[1] * prijs[x[0]])],
        historie=st["historie"], transacties=st["transacties"][-40:], signaal=st.get("laatste_signaal"),
        namen=S.NAMEN, regels=dict(top=TOP, score="gemiddelde rendement 1, 3, 6 en 12 maanden",
                                   filter="alleen kopen als sterker dan de geldmarkt"),
    )
    json.dump(stand, open(STAND, "w"), indent=1)
    print(f"{vandaag}: waarde €{w:,.2f} | wereld-ETF €{b:,.2f}" + (" | herverdeeld" if signaal else ""))


if __name__ == "__main__":
    main()
