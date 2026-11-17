#!/usr/bin/env python3
"""Portefeuille DEGIRO - koersen ophalen.

Haalt via Yahoo Finance (openbaar, geen account) de laatste koers en de vorige slotkoers op
van de vijf posities, plus de EUR/USD-koers, en schrijft alles naar docs/portefeuille.json.
Het overzicht (artifact) leest dat bestand rechtstreeks uit GitHub.

Aantallen en aankoopwaarden staan in portefeuille/posities.json. Bij een aan- of verkoop
alleen dat bestand aanpassen.
"""
import datetime as dt
import json
import os
import time

import yfinance as yf

HIER = os.path.dirname(os.path.abspath(__file__))
POS = os.path.join(HIER, "posities.json")
UIT = os.path.join(HIER, "..", "docs", "portefeuille.json")
MAX_OUD_DAGEN = 5  # een koers ouder dan dit (kalenderdagen) wordt niet gebruikt


def koers(ticker):
    """Geeft (laatste koers, datum, vorige slotkoers) of None."""
    for poging in range(3):
        try:
            df = yf.Ticker(ticker).history(period="10d", interval="1d", auto_adjust=False)
            df = df.dropna(subset=["Close"])
            if len(df) < 2:
                raise RuntimeError("te weinig koersen")
            laatst, vorig = df.iloc[-1], df.iloc[-2]
            datum = df.index[-1].date()
            return float(laatst["Close"]), datum, float(vorig["Close"])
        except Exception as e:  # netwerk / Yahoo hapert soms even
            print(ticker, "poging", poging + 1, "mislukt:", e)
            time.sleep(5)
    return None


def main():
    cfg = json.load(open(POS))
    vorige = {}
    if os.path.exists(UIT):
        try:
            vorige = {p["id"]: p for p in json.load(open(UIT)).get("posities", [])}
        except Exception:
            pass

    fx = koers("EURUSD=X")
    if not fx:
        raise SystemExit("Geen EUR/USD-koers; deze run wordt overgeslagen.")
    eurusd, fx_datum, eurusd_vorig = fx

    vandaag = dt.date.today()
    uit, fouten = [], []
    for p in cfg["posities"]:
        r = None
        for t in p["tickers"]:  # eerste ticker die werkt
            r = koers(t)
            if r and (vandaag - r[1]).days <= MAX_OUD_DAGEN:
                bron = t
                break
            r = None
        if not r:
            fouten.append(p["id"])
            if p["id"] in vorige:  # oude stand laten staan, maar wel gemarkeerd
                oud = dict(vorige[p["id"]])
                oud["verouderd"] = True
                uit.append(oud)
            continue
        k, datum, kv = r
        usd = p["munt"] == "USD"
        v = p["aantal"] * (k / eurusd if usd else k)
        v_vorig = p["aantal"] * (kv / eurusd_vorig if usd else kv)
        uit.append({
            "id": p["id"], "naam": p["naam"], "soort": p["soort"], "munt": p["munt"],
            "ticker": bron, "aantal": p["aantal"], "gak": p["gak"],
            "koers": round(k, 4), "koersdatum": datum.isoformat(), "vorige_slot": round(kv, 4),
            "waarde": round(v, 2), "aankoopwaarde": p["aankoopwaarde"],
            "resultaat": round(v - p["aankoopwaarde"], 2),
            "vandaag": round(v - v_vorig, 2),
            "verouderd": False,
        })
        print(f'{p["id"]:10s} {bron:9s} {datum} koers {k:.3f} {p["munt"]}  waarde €{v:,.2f}  resultaat €{v - p["aankoopwaarde"]:+,.2f}')

    if not uit:
        raise SystemExit("Geen enkele koers gevonden; niets opgeslagen.")

    waarde = sum(p["waarde"] for p in uit)
    kost = sum(p["aankoopwaarde"] for p in uit)
    stand = {
        "bijgewerkt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "eurusd": round(eurusd, 5), "eurusd_datum": fx_datum.isoformat(),
        "vrij_saldo": cfg["vrij_saldo"], "gerealiseerd": cfg["gerealiseerd"],
        "waarde": round(waarde, 2), "aankoopwaarde": round(kost, 2),
        "ongerealiseerd": round(waarde - kost, 2),
        "vandaag": round(sum(p["vandaag"] for p in uit if not p["verouderd"]), 2),
        "niet_bijgewerkt": fouten,
        "posities": uit,
    }
    json.dump(stand, open(UIT, "w"), ensure_ascii=False, indent=1)
    print(f"Totaal €{waarde:,.2f} · ongerealiseerd €{waarde - kost:+,.2f} · EUR/USD {eurusd:.4f}"
          + (f" · NIET bijgewerkt: {fouten}" if fouten else ""))


if __name__ == "__main__":
    main()
