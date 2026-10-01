#!/usr/bin/env python3
"""Crypto-proefagent: papieren handel in het brede Crypto.com-aanbod (in euro's).

Gebruik:
  python3 bot.py --state state.json --tickers tickers.json --out new_state.json [--now <unix>]

- state.json   : het document agent/state uit de artifact-database
- tickers.json : de volledige uitvoer van Crypto.com get_tickers (zonder filter), {"data": [...]}
- new_state.json: bijgewerkte state om terug te schrijven
Er wordt niets gekocht of verkocht met echt geld.

Welke munten mogen meedoen (het "universum") bepaalt het script zelf, elke check opnieuw:
- alleen munten met een dollarnotering op Crypto.com;
- geen stablecoins, goudtokens, verpakte/gestakete varianten, memecoins of ingestorte projecten;
- genoeg handel: minimaal $250.000 per 24 uur om erin te komen, minimaal $100.000 om erin te blijven;
- nieuwe munten worden eerst ~7 dagen gevolgd (inloop) voordat de agent ze mag kopen;
- niet kopen bij een groot verschil tussen bied- en laatprijs (>1%) of na een crash (>40% onder het
  hoogste punt van de afgelopen week).
"""
import argparse, json, re, time, datetime as dt

NAMES = {"BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "XRP": "XRP", "ADA": "Cardano",
         "LINK": "Chainlink", "AVAX": "Avalanche", "DOT": "Polkadot", "LTC": "Litecoin",
         "QNT": "Quant", "CRO": "Cronos", "NEAR": "NEAR", "HBAR": "Hedera", "AAVE": "Aave",
         "SUI": "Sui", "ARB": "Arbitrum", "XLM": "Stellar", "WLD": "Worldcoin", "MOVR": "Moonriver",
         "FIL": "Filecoin", "FET": "Fetch.ai", "ICP": "Internet Computer", "ARK": "Ark", "HFT": "Hashflow",
         "ENA": "Ethena", "GALA": "Gala", "BCH": "Bitcoin Cash", "ONDO": "Ondo", "VIRTUAL": "Virtuals",
         "TAO": "Bittensor", "UNI": "Uniswap", "W": "Wormhole", "ATOM": "Cosmos", "STX": "Stacks",
         "JASMY": "JasmyCoin", "INJ": "Injective", "LDO": "Lido", "VET": "VeChain", "POL": "Polygon",
         "JUP": "Jupiter", "APT": "Aptos", "ALGO": "Algorand", "HYPE": "Hyperliquid", "OP": "Optimism",
         "PYTH": "Pyth", "FLR": "Flare", "AR": "Arweave", "RENDER": "Render", "ETC": "Ethereum Classic",
         "IMX": "Immutable", "GRT": "The Graph", "CRV": "Curve", "TRX": "TRON", "TON": "Toncoin"}

EXCLUDE = {
    # stablecoins en goud: bewegen (bijna) niet
    "USDT", "USDC", "DAI", "FDUSD", "TUSD", "PYUSD", "USDE", "USDS", "USD1", "RLUSD", "EURC", "EURQ",
    "USDG", "BUSD", "USDP", "GUSD", "FRAX", "PAXG", "XAUT",
    # verpakte en gestakete varianten van andere munten
    "WBTC", "WETH", "CBBTC", "STETH", "WSTETH", "CBETH", "JITOSOL", "MSOL", "BNSOL", "LBTC", "RETH",
    # memecoins
    "DOGE", "SHIB", "PEPE", "BONK", "WIF", "FLOKI", "TRUMP", "FARTCOIN", "PENGU", "CASHCAT", "BASECAT",
    "ELON", "TURBO", "WEN", "COQ", "POPCAT", "MEW", "BRETT", "MOG", "GOAT", "SPX", "NEIRO", "PNUT",
    "MOODENG", "USELESS", "GOATED", "CAW", "DOG", "BOME", "MEME", "BABYDOGE", "MELANIA", "PUMP", "BAN",
    # ingestorte projecten
    "LUNC", "USTC", "LUNA", "FTT",
}

DEFAULT_PARAMS = {
    "startKapitaal": 1000.0,
    "kosten": 0.0025,          # 0,25% per transactie, plus de helft van het bied-laatverschil
    "maxSpread": 0.01,         # niet kopen als bied-laatverschil groter is dan 1%
    "volInstap": 250000.0,     # min. 24-uurs handel ($) om in het universum te komen
    "volBlijf": 100000.0,      # min. 24-uurs handel ($) om erin te blijven
    "crashGrens": 0.40,        # niet kopen als koers >40% onder het weekhoogste staat
    "maxPosities": 4,
    "maxUniversum": 40,        # hooguit 40 munten tegelijk volgen (de meest verhandelde)
    "emaKort": 16, "emaLang": 40, "rsiPeriode": 14,
    "trendStop": 0.06, "trendTrailing": 0.07,
    "veerInstapRsi": 30, "veerUitstapRsi": 55,
    "veerWinst": 0.04, "veerStop": 0.05, "veerMaxDagen": 7,
    "weekVerliesStop": 0.08,
    "maxSprong": 0.25,
    "maxOuderdom": 1800,       # koers ouder dan 30 minuten = niet gebruiken
    "maxPunten": 60, "maxEquity": 1000, "maxTrades": 300, "maxLog": 150,
}

def eur(v):
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if v < 0 else "") + "€" + s

def naam(c): return NAMES.get(c, c)

def ema(vals, n):
    if len(vals) < n: return None
    k = 2 / (n + 1); e = sum(vals[:n]) / n
    out = [None] * (n - 1) + [e]
    for v in vals[n:]:
        e = v * k + e * (1 - k); out.append(e)
    return out

def rsi(vals, n=14):
    if len(vals) < n + 1: return None
    g = [max(0, vals[i] - vals[i-1]) for i in range(1, len(vals))]
    l = [max(0, vals[i-1] - vals[i]) for i in range(1, len(vals))]
    ag = sum(g[:n]) / n; al = sum(l[:n]) / n
    out = [None] * n + [100 if al == 0 else 100 - 100 / (1 + ag / al)]
    for gi, li in zip(g[n:], l[n:]):
        ag = (ag * (n - 1) + gi) / n; al = (al * (n - 1) + li) / n
        out.append(100 if al == 0 else 100 - 100 / (1 + ag / al))
    return out

def _f(x):
    try: return float(x)
    except (TypeError, ValueError): return 0.0

def _ts(s):
    return int(dt.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()) if s else None

def parse_tickers(text, now, max_age):
    """Volledige get_tickers-uitvoer -> {munt: {prijs (EUR), spread, vol (USD)}}, wisselkoers, meldingen."""
    m = re.search(r"\{.*\}", text, re.S)
    data = json.loads(m.group(0)) if m else {}
    rows = data.get("data") if isinstance(data, dict) else data
    if not rows: raise ValueError("Geen tickerlijst gevonden.")
    T = {r.get("instrument_name"): r for r in rows if isinstance(r, dict)}
    for k in ("BTCEUR", "BTCUSD"):
        if k not in T: raise ValueError(f"{k} ontbreekt; wisselkoers niet te bepalen.")
        t = _ts(T[k].get("timestamp"))
        if t and abs(now - t) > max_age: raise ValueError(f"{k} is te oud; check overgeslagen.")
    be = T["BTCEUR"]
    eur_mid = (_f(be.get("best_bid")) + _f(be.get("best_ask"))) / 2 or _f(be.get("last"))
    fx = eur_mid / _f(T["BTCUSD"]["last"])
    if not 0.6 < fx < 1.4: raise ValueError(f"Onlogische wisselkoers ({fx:.4f}).")
    out, oud = {}, 0
    for name, r in T.items():
        if not name or not name.endswith("USD"): continue
        base = name[:-3]
        if not base.isalnum() or base.endswith("PY"): continue
        last = _f(r.get("last"))
        if last <= 0: continue
        t = _ts(r.get("timestamp"))
        if t and abs(now - t) > max_age: oud += 1; continue
        bid, ask = _f(r.get("best_bid")), _f(r.get("best_ask"))
        spread = (ask - bid) / ((ask + bid) / 2) if bid > 0 and ask > bid else 0.0
        vol = _f(r.get("volume_value")) + _f((T.get(base + "USDT") or {}).get("volume_value"))
        out[base] = {"prijs": last * fx, "spread": spread, "vol": vol}
    notes = [f"{oud} koersen waren ouder dan 30 minuten en zijn niet gebruikt."] if oud > 100 else []
    return out, fx, notes

def week_start(t):
    d = dt.datetime.fromtimestamp(t, dt.timezone.utc)
    return int((d - dt.timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

def tijd(t):
    return dt.datetime.fromtimestamp(t, dt.timezone(dt.timedelta(hours=2))).strftime("%d-%m %H:%M")

def run(state, tick, now, notes=()):
    P = {**DEFAULT_PARAMS, **state.get("params", {})}
    for k, v in DEFAULT_PARAMS.items():          # nieuwe regels gaan voor oude waarden
        if k in ("maxPunten",): P[k] = v
    state["params"] = P
    for k, v in (("cash", P["startKapitaal"]), ("positions", []), ("trades", []), ("log", []),
                 ("equity", []), ("prices", {}), ("universe", {}),
                 ("stats", {"kosten": 0.0, "gesloten": 0, "winst": 0, "verlies": 0})):
        state.setdefault(k, v)
    msgs = list(notes)
    held = {x["coin"] for x in state["positions"]}
    bench = set((state.get("start") or {}).get("mandje", {}).keys())
    U = state["universe"]

    # 1. Universum bijwerken
    nieuw, weg = [], []
    if not U:  # eerste keer: bestaande munten met geschiedenis meteen opnemen
        for c in state["prices"]: U[c] = {"since": now}
    kand = sorted((c for c, t in tick.items() if c not in EXCLUDE and c not in U and t["vol"] >= P["volInstap"]),
                  key=lambda c: -tick[c]["vol"])
    for c in kand:
        if len(U) >= P["maxUniversum"]: break
        U[c] = {"since": now}; nieuw.append(naam(c))
    for c in list(U):
        t = tick.get(c)
        if c in EXCLUDE or t is None or t["vol"] < P["volBlijf"]:
            if c not in held: weg.append(naam(c))
            del U[c]
    for c in U: U[c]["vol"] = round(tick.get(c, {}).get("vol", 0))
    if nieuw: msgs.append("Nieuw gevolgd (eerst ~7 dagen inloop): " + ", ".join(sorted(nieuw)) + ".")
    if weg: msgs.append("Niet meer gevolgd wegens te weinig handel: " + ", ".join(sorted(weg)) + ".")

    # 2. Koersen bijhouden voor universum, bezit en vergelijkingsmandje
    volg = set(U) | held | bench
    last, spreads = {}, {}
    for c in volg:
        t = tick.get(c)
        series = state["prices"].setdefault(c, [])
        if not t: continue
        p = t["prijs"]
        if series and abs(p / series[-1][1] - 1) > P["maxSprong"]:
            msgs.append(f"{naam(c)}: koers wijkt te sterk af van de vorige check; genegeerd als mogelijke datafout.")
            continue
        series.append([now, float(f"{p:.6g}")]); del series[:-P["maxPunten"]]
        last[c] = p; spreads[c] = t["spread"]
    for c in list(state["prices"]):
        if c not in volg: del state["prices"][c]

    def price_of(c):
        s = state["prices"].get(c) or []
        return s[-1][1] if s else None

    def equity():
        return state["cash"] + sum(x["qty"] * (price_of(x["coin"]) or x["entry"]) for x in state["positions"])

    # 3. Startpunt en vergelijkingsmandje (alleen bij een nieuwe proef)
    if not state.get("start"):
        top = [c for c in ("BTC", "ETH", "SOL", "XRP", "ADA", "LINK", "AVAX", "DOT", "LTC") if c in last]
        per = P["startKapitaal"] * (1 - P["kosten"]) / len(top)
        state["start"] = {"t": now, "equity": P["startKapitaal"], "mandje": {c: per / last[c] for c in top}}
        msgs.append(f"Proef gestart met {eur(P['startKapitaal'])} fictief geld.")

    # 4. Weekbewaking
    ws = week_start(now)
    if state.get("week", {}).get("start") != ws:
        state["week"] = {"start": ws, "equity": equity()}
        if state.get("paused"):
            state["paused"] = False
            msgs.append("Nieuwe week: pauze opgeheven, de agent mag weer kopen.")
    if not state.get("paused") and equity() < state["week"]["equity"] * (1 - P["weekVerliesStop"]):
        state["paused"] = True
        msgs.append(f"Weekverlies groter dan {int(P['weekVerliesStop']*100)}%: geen nieuwe aankopen tot maandag. Verkopen blijven mogelijk.")

    def trade(c, side, qty, price, potje, reason, pos=None):
        kostpct = P["kosten"] + spreads.get(c, 0) / 2
        bruto = qty * price; kost = bruto * kostpct
        state["stats"]["kosten"] += kost
        rec = {"id": f"{now}-{c}-{side}", "t": now, "coin": c, "naam": naam(c), "potje": potje, "side": side,
               "prijs": float(f"{price:.6g}"), "aantal": qty, "bedrag": round(bruto, 2), "kosten": round(kost, 2), "reden": reason}
        if side == "koop":
            state["cash"] -= bruto + kost
        else:
            state["cash"] += bruto - kost
            pnl = bruto - kost - pos["inleg"]
            rec["resultaat"] = round(pnl, 2)
            state["stats"]["gesloten"] += 1
            state["stats"]["winst" if pnl > 0 else "verlies"] += 1
        state["trades"].append(rec); del state["trades"][:-P["maxTrades"]]
        return rec, kostpct

    # 5. Posities beheren, daarna kansen verzamelen
    kansen, trend_cnt, inloop, geblokt = [], 0, 0, 0
    for c in sorted(volg):
        if c not in last: continue
        closes = [x[1] for x in state["prices"][c]]
        p = closes[-1]
        e_k = ema(closes, P["emaKort"]); e_l = ema(closes, P["emaLang"]); r = rsi(closes, P["rsiPeriode"])
        ready = e_l is not None and r is not None and len(closes) >= P["emaLang"] + 1
        pos = next((x for x in state["positions"] if x["coin"] == c), None)
        if pos:
            pos["piek"] = max(pos.get("piek", pos["entry"]), p)
            reden = None
            if pos["potje"] == "trend":
                if p <= pos["entry"] * (1 - P["trendStop"]):
                    reden = f"Stop: koers meer dan {int(P['trendStop']*100)}% onder de instapprijs gezakt."
                elif p <= pos["piek"] * (1 - P["trendTrailing"]):
                    reden = f"Winst/verlies vastgezet: koers {int(P['trendTrailing']*100)}% onder het hoogste punt sinds aankoop."
                elif ready and (e_k[-1] < e_l[-1] or p < e_l[-1]):
                    reden = "Trend voorbij: de koers zakte onder het lange gemiddelde."
            else:
                dagen = (now - pos["entryT"]) / 86400
                if p >= pos["entry"] * (1 + P["veerWinst"]):
                    reden = f"Winstdoel gehaald: {int(P['veerWinst']*100)}% boven de instapprijs."
                elif p <= pos["entry"] * (1 - P["veerStop"]):
                    reden = f"Stop: koers verder gezakt dan {int(P['veerStop']*100)}% onder de instapprijs."
                elif ready and r[-1] >= P["veerUitstapRsi"]:
                    reden = "Terugvering voltooid: de koers is hersteld naar een normaal niveau."
                elif dagen >= P["veerMaxDagen"]:
                    reden = f"Te lang vastgehouden (meer dan {P['veerMaxDagen']} dagen) zonder herstel."
            if c not in U and not reden:
                reden = "Munt valt buiten de selectie (te weinig handel); positie gesloten."
            if reden:
                rec, _ = trade(c, "verkoop", pos["qty"], p, pos["potje"], reden, pos)
                state["positions"].remove(pos)
                if reden.startswith("Stop"):
                    state.setdefault("cooldown", {})[c] = now + 86400
                msgs.append(f"VERKOCHT {naam(c)} voor {eur(rec['bedrag'])}, resultaat {eur(rec['resultaat'])}. {reden}")
            continue
        if c not in U: continue
        if not ready:
            inloop += 1; continue
        trend_up = e_k[-1] > e_l[-1] and p > e_l[-1]
        trend_cnt += trend_up
        if now < state.get("cooldown", {}).get(c, 0): continue
        if spreads.get(c, 0) > P["maxSpread"] or p < max(closes[-42:]) * (1 - P["crashGrens"]):
            geblokt += 1; continue
        if trend_up and closes[-2] <= e_k[-2] and p > e_k[-1]:
            kansen.append((0, -(p / e_l[-1] - 1), c, "trend", "Trend omhoog en de koers veert net weer boven het korte gemiddelde uit."))
        elif r[-1] < P["veerInstapRsi"]:
            kansen.append((1, r[-1], c, "terugveer", "Scherpe daling: de koers is ongewoon laag gezakt, kans op terugvering."))

    # 6. Sterkste kansen kopen zolang er plek en geld is
    kansen.sort()
    overgeslagen = 0
    for _, _, c, potje, uitleg in kansen:
        if state.get("paused") or len(state["positions"]) >= P["maxPosities"]:
            overgeslagen += 1; continue
        kp = P["kosten"] + spreads.get(c, 0) / 2
        budget = min(state["cash"] / (1 + kp), equity() / P["maxPosities"])
        if budget < 25:
            overgeslagen += 1; continue
        p = last[c]
        rec, _ = trade(c, "koop", budget / p, p, potje, uitleg)
        state["positions"].append({"coin": c, "potje": potje, "qty": budget / p, "entry": p, "entryT": now,
                                   "piek": p, "inleg": round(budget * (1 + kp), 2)})
        msgs.append(f"GEKOCHT {naam(c)} voor {eur(rec['bedrag'])} ({'trendvolgen' if potje=='trend' else 'terugveren'}). {uitleg}")

    # 7. Stand bijwerken
    eq = equity()
    mandje = None
    if state.get("start"):
        mandje = sum(q * (price_of(c) or 0) for c, q in state["start"]["mandje"].items())
    state["equity"].append([now, round(eq, 2), round(mandje, 2) if mandje else None])
    del state["equity"][:-P["maxEquity"]]
    actief = len(U) - inloop
    state["universeInfo"] = {"totaal": len(U), "inloop": inloop, "actief": actief, "trend": trend_cnt}
    state["names"] = {c: naam(c) for c in set(U) | held | bench}
    if not any(m.startswith(("GEKOCHT", "VERKOCHT")) for m in msgs):
        delen = [f"{len(state['positions'])} posities vastgehouden" if state["positions"] else "geen posities",
                 f"{len(U)} munten gevolgd, waarvan {inloop} nog in inloop",
                 f"{trend_cnt} van {actief} in een stijgende trend, maar geen goed instapmoment"]
        if geblokt: delen.append(f"{geblokt} geblokkeerd (te groot prijsverschil of recente crash)")
        if overgeslagen: delen.append(f"{overgeslagen} kans(en) overgeslagen (vol, gepauzeerd of te weinig saldo)")
        msgs.append("Geen transactie: " + "; ".join(delen) + ".")
    for m in msgs:
        state["log"].append({"t": now, "msg": m})
    del state["log"][:-P["maxLog"]]
    state["lastRun"] = now
    state["runs"] = state.get("runs", 0) + 1
    return state, msgs

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", required=True); ap.add_argument("--tickers", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--now", type=int)
    a = ap.parse_args()
    state = json.load(open(a.state))
    now = a.now or int(time.time())
    P = {**DEFAULT_PARAMS, **state.get("params", {})}
    tick, fx, notes = parse_tickers(open(a.tickers).read(), now, P["maxOuderdom"])
    state, msgs = run(state, tick, now, notes)
    json.dump(state, open(a.out, "w"), separators=(",", ":"))
    print(f"Check {tijd(now)} — waarde {eur(state['equity'][-1][1])} (1 USD = €{fx:.4f})")
    for m in msgs: print("-", m)
