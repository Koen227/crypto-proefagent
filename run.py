#!/usr/bin/env python3
"""Eén check van de Crypto Proefagent, zoals GitHub hem elke 15 minuten draait.

- Haalt alle live koersen op bij de openbare Bitvavo-API (geen account of sleutel nodig).
- Elke 15 minuten: bewaken (stopverliezen, winst vastzetten, nieuws).
- Elke 4 uur: alle euromarkten scannen en kansen zoeken, met orderboek en koersgeschiedenis van Bitvavo.
- Extra signalen: Fear & Greed-index, nieuwskoppen (CoinDesk, Cointelegraph) en open interest
  van perpetual futures (Crypto.com).
- Schrijft data/state.json (volledige stand) en docs/stand.json (voor het dashboard),
  maar alleen als er iets veranderd is.

Er wordt nergens echt gehandeld: dit is papieren handel met fictief geld.
"""
import email.utils, json, os, sys, time, urllib.request, xml.etree.ElementTree as ET

import bot

HIER = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HIER, "data", "state.json")
STAND = os.path.join(HIER, "docs", "stand.json")
BITVAVO = "https://api.bitvavo.com/v2"
CRYPTOCOM = "https://api.crypto.com/exchange/v1/public/get-tickers"
FNG_API = "https://api.alternative.me/fng/?limit=1"
RSS = [("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
       ("Cointelegraph", "https://cointelegraph.com/rss")]


def haal(url, pogingen=3, json_=True):
    fout = None
    for i in range(pogingen):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "crypto-proefagent/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode("utf-8", "replace")
            return json.loads(body) if json_ else body
        except Exception as e:
            fout = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"{url} niet bereikbaar: {fout}")


def boek(c):
    return haal(f"{BITVAVO}/{c}-EUR/book?depth=25", pogingen=2)


def historie(c):
    """Laatste 4-uurskaarsen als [t_sluiting, slotkoers, handel in EUR], oud -> nieuw."""
    rows = haal(f"{BITVAVO}/{c}-EUR/candles?interval=4h&limit=60", pogingen=2)
    time.sleep(0.05)
    nu = time.time()
    out = []
    for t, o, h, l, cl, v in reversed(rows):
        sluit = int(t) // 1000 + 14400
        if sluit <= nu:  # alleen afgesloten kaarsen
            out.append([sluit, float(cl), float(v) * float(cl)])
    return out


def open_interest():
    try:
        rows = haal(CRYPTOCOM, pogingen=2)["result"]["data"]
        out = {}
        for r in rows:
            i = r.get("i") or ""
            if i.endswith("USD-PERP") and bot._f(r.get("oi")) > 0:
                out[i[:-8]] = bot._f(r.get("oi"))
        return out
    except Exception as e:
        print(f"Futuresgegevens niet beschikbaar: {e}")
        return None


def fear_greed():
    try:
        return bot.parse_fng(haal(FNG_API, pogingen=2, json_=False))
    except Exception as e:
        print(f"Fear & Greed niet beschikbaar: {e}")
        return None


def nieuws():
    items = []
    for bron, url in RSS:
        try:
            root = ET.fromstring(haal(url, pogingen=2, json_=False))
            for it in root.iter("item"):
                titel = (it.findtext("title") or "").strip()
                datum = it.findtext("pubDate")
                t = int(email.utils.parsedate_to_datetime(datum).timestamp()) if datum else None
                if titel:
                    items.append({"titel": titel, "t": t, "bron": bron})
        except Exception as e:
            print(f"Nieuws van {bron} niet beschikbaar: {e}")
    return items


def schrijf(pad, data):
    os.makedirs(os.path.dirname(pad), exist_ok=True)
    tmp = pad + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    os.replace(tmp, pad)


def main():
    now = int(time.time())
    state = json.load(open(STATE))
    P = {**bot.DEFAULT_PARAMS, **state.get("params", {})}
    scan = (now // P["scanInterval"] > state.get("lastScan", 0) // P["scanInterval"]) or state.get("bron") != "bitvavo"
    if "--scan" in sys.argv: scan = True

    tick, notes = bot.parse_bitvavo(haal(f"{BITVAVO}/ticker/24h"), now, P["maxOuderdom"])
    extra = {"fng": fear_greed(), "news": nieuws()}
    if scan:
        extra.update(boek=boek, historie=historie, oi=open_interest())
    state, msgs, gewijzigd = bot.run(state, tick, now, notes, scan=scan, **extra)

    print(f"{'Scan' if scan else 'Bewaking'} {bot.tijd(now)} — {len(tick)} markten")
    for m in msgs:
        print("-", m)
    if gewijzigd:
        schrijf(STATE, state)
        schrijf(STAND, bot.samenvatting(state))
    else:
        print("Niets veranderd; niets opgeslagen.")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Check mislukt: {e}", file=sys.stderr)
        sys.exit(1)
