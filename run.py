#!/usr/bin/env python3
"""Eén check van de Crypto Proefagent, zoals GitHub hem elke 4 uur draait.

1. Haalt alle live koersen op bij de openbare Crypto.com-API (geen account of sleutel nodig).
2. Draait de handelsregels uit bot.py op de opgeslagen stand in docs/state.json.
3. Schrijft de nieuwe stand terug; het dashboard (docs/index.html) leest dat bestand.

Er wordt nergens echt gehandeld: dit is papieren handel met fictief geld.
"""
import datetime as dt, json, os, sys, time, urllib.request

import bot

API = "https://api.crypto.com/exchange/v1/public/get-tickers"
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "state.json")


def haal_koersen(pogingen=3):
    laatste_fout = None
    for i in range(pogingen):
        try:
            req = urllib.request.Request(API, headers={"User-Agent": "crypto-proefagent/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.load(r)
            if body.get("code") != 0:
                raise ValueError(f"API-fout: code {body.get('code')}")
            return body["result"]["data"]
        except Exception as e:  # netwerk of API tijdelijk niet bereikbaar
            laatste_fout = e
            time.sleep(10 * (i + 1))
    raise RuntimeError(f"Koersen niet op te halen: {laatste_fout}")


FNG_API = "https://api.alternative.me/fng/?limit=1"
RSS = [("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
       ("Cointelegraph", "https://cointelegraph.com/rss")]


def haal_tekst(url):
    req = urllib.request.Request(url, headers={"User-Agent": "crypto-proefagent/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def haal_fng():
    try:
        return bot.parse_fng(haal_tekst(FNG_API))
    except Exception as e:
        print(f"Fear & Greed niet beschikbaar: {e}")
        return None


def haal_nieuws():
    import email.utils, xml.etree.ElementTree as ET
    items = []
    for bron, url in RSS:
        try:
            root = ET.fromstring(haal_tekst(url))
            for it in root.iter("item"):
                titel = (it.findtext("title") or "").strip()
                datum = it.findtext("pubDate")
                t = int(email.utils.parsedate_to_datetime(datum).timestamp()) if datum else None
                if titel:
                    items.append({"titel": titel, "t": t, "bron": bron})
        except Exception as e:
            print(f"Nieuws van {bron} niet beschikbaar: {e}")
    return items


def naar_ticker_formaat(rows):
    """Zet de korte API-velden om naar het formaat dat bot.parse_tickers verwacht."""
    out = []
    for r in rows:
        naam = (r.get("i") or "").replace("_", "")
        t = r.get("t")
        ts = dt.datetime.fromtimestamp(t / 1000, dt.timezone.utc).isoformat().replace("+00:00", "Z") if t else None
        out.append({"instrument_name": naam, "last": r.get("a"), "best_bid": r.get("b"),
                    "best_ask": r.get("k"), "volume_value": r.get("vv"), "timestamp": ts,
                    "open_interest": r.get("oi")})
    return {"data": out}


def main():
    now = int(time.time())
    state = json.load(open(STATE))
    P = {**bot.DEFAULT_PARAMS, **state.get("params", {})}
    tickers = naar_ticker_formaat(haal_koersen())
    tick, fx, notes = bot.parse_tickers(json.dumps(tickers), now, P["maxOuderdom"])
    state, msgs = bot.run(state, tick, now, notes, fng=haal_fng(), news=haal_nieuws())
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, separators=(",", ":"))
    os.replace(tmp, STATE)
    print(f"Check {bot.tijd(now)} — waarde {bot.eur(state['equity'][-1][1])} (1 USD = €{fx:.4f})")
    for m in msgs:
        print("-", m)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Check mislukt: {e}", file=sys.stderr)
        sys.exit(1)
