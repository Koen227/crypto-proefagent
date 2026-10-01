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
    # momentum-uitbraak (apart potje)
    "momMaxPosities": 1, "momBudget": 150.0,
    "momVolFactor": 3.0,       # 24-uurs handel minstens 3x het weekgemiddelde
    "momStop": 0.08, "momTrailing": 0.10, "momMaxDagen": 14,
    # extra remmen: "uit", "schaduw" (alleen noteren) of "aan" (echt tegenhouden)
    "filterNieuws": "aan",     # geen aankoop bij slecht nieuws (hack, delisting, rechtszaak...) in de laatste 48 uur
    "filterFG": "schaduw",     # geen trend-/momentumaankoop bij extreme hebzucht in de markt
    "filterFutures": "schaduw",# geen aankoop als hefboominzet en koers samen hard oplopen
    "fgHebzucht": 80,          # Fear & Greed-index vanaf 80 = extreme hebzucht
    "oiStijging": 0.25, "oiKoersStijging": 0.10,  # +25% open interest en +10% koers in 24 uur
    "nieuwsUren": 48,
    "maxSprong": 0.25,
    "maxOuderdom": 1800,       # koers ouder dan 30 minuten = niet gebruiken
    "maxPunten": 60, "maxEquity": 1000, "maxTrades": 300, "maxLog": 150,
}

def eur(v):
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if v < 0 else "") + "€" + s

def naam(c): return NAMES.get(c, c)

NEGATIEF = ("hack", "hacked", "exploit", "drained", "stolen", "delist", "lawsuit", "sued", "charges",
            "fraud", "rug pull", "rugpull", "insolven", "bankrupt", "halts withdrawals", "suspends withdrawals",
            "pauses withdrawals", "security incident", "vulnerability", "attack", "scam", "ponzi", "investigation")
FILTERNAAM = {"nieuws": "slecht nieuws", "fg": "extreme hebzucht", "futures": "veel hefboom"}

def noemt_munt(titel, c):
    """Wordt munt c genoemd in de kop? Ticker in hoofdletters (min. 3 tekens) of de naam met hoofdletter."""
    if len(c) >= 3 and re.search(rf"(?<![A-Za-z0-9$]){re.escape(c)}(?![A-Za-z0-9])", titel):
        return True
    n = NAMES.get(c)
    return bool(n and len(n) >= 3 and n != c and re.search(rf"\b{re.escape(n)}\b", titel))

POTNAAM = {"trend": "trendvolgen", "terugveer": "terugveren", "momentum": "momentum-uitbraak"}

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
    for name, r in T.items():
        n = (name or "").replace("-", "")
        if n.endswith("USDPERP") and n[:-7] in out:
            oi = _f(r.get("open_interest"))
            if oi > 0: out[n[:-7]]["oi"] = oi
    notes = [f"{oud} koersen waren ouder dan 30 minuten en zijn niet gebruikt."] if oud > 100 else []
    return out, fx, notes

def parse_fng(text):
    try:
        m = re.search(r"\{.*\}", text, re.S); d = json.loads(m.group(0))["data"][0]
        return {"waarde": int(d["value"]), "label": d.get("value_classification", ""), "t": int(d.get("timestamp", 0))}
    except Exception:
        return None

def week_start(t):
    d = dt.datetime.fromtimestamp(t, dt.timezone.utc)
    return int((d - dt.timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())

def tijd(t):
    return dt.datetime.fromtimestamp(t, dt.timezone(dt.timedelta(hours=2))).strftime("%d-%m %H:%M")

def run(state, tick, now, notes=(), fng=None, news=None):
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
        vs = state.setdefault("vols", {}).setdefault(c, [])
        vs.append(round(t["vol"])); del vs[:-P["maxPunten"]]
        last[c] = p; spreads[c] = t["spread"]
    for c in list(state["prices"]):
        if c not in volg: del state["prices"][c]
    for c in list(state.get("vols", {})):
        if c not in volg: del state["vols"][c]

    # 2b. Signalen: open interest, Fear & Greed, nieuws
    for c in volg:
        t = tick.get(c)
        if t and t.get("oi"):
            o = state.setdefault("oi", {}).setdefault(c, []); o.append(float(f"{t['oi']:.6g}")); del o[:-P["maxPunten"]]
    for c in list(state.get("oi", {})):
        if c not in volg: del state["oi"][c]
    if fng is not None:
        state["fng"] = fng
    alarm = state.setdefault("nieuwsAlarm", {})
    for c in list(alarm):
        if alarm[c]["tot"] < now: del alarm[c]
    if news:
        gezien = set(state.get("nieuwsGezien", []))
        lijst = state.setdefault("nieuws", [])
        for it in sorted(news, key=lambda x: x.get("t") or 0):
            titel, t_it = it.get("titel") or "", it.get("t") or now
            key = titel[:120]
            if not titel or key in gezien or now - t_it > P["nieuwsUren"] * 3600: continue
            gezien.add(key)
            munten = sorted(c for c in set(U) | held if noemt_munt(titel, c))
            if not munten: continue
            neg = any(w in titel.lower() for w in NEGATIEF)
            rem = [c for c in munten if c not in ("BTC", "ETH")] if neg else []  # BTC/ETH staan in bijna elk bericht
            lijst.append({"t": t_it, "titel": titel, "bron": it.get("bron", ""), "munten": munten, "negatief": neg, "rem": rem})
            if neg:
                for c in rem:
                    alarm[c] = {"tot": t_it + P["nieuwsUren"] * 3600, "titel": titel}
                    if c in held:
                        msgs.append(f"Let op: slecht nieuws over {naam(c)}, dat de agent bezit: \"{titel}\". Verkopen gebeurt nog via de gewone regels.")
        del lijst[:-20]
        state["nieuwsGezien"] = list(gezien)[-100:]

    def filters(c, potje, closes):
        """Geeft [(filter, reden)] terug van remmen die deze aankoop zouden tegenhouden."""
        hits = []
        if P["filterNieuws"] != "uit" and c in alarm:
            hits.append(("nieuws", f"slecht nieuws: \"{alarm[c]['titel'][:90]}\""))
        f = state.get("fng")
        if P["filterFG"] != "uit" and f and potje in ("trend", "momentum") and f.get("waarde", 0) >= P["fgHebzucht"]:
            hits.append(("fg", f"extreme hebzucht in de markt (Fear & Greed {f['waarde']})"))
        o = state.get("oi", {}).get(c, [])
        if P["filterFutures"] != "uit" and len(o) >= 7 and len(closes) >= 7 and o[-7] > 0:
            oi24, k24 = o[-1] / o[-7] - 1, closes[-1] / closes[-7] - 1
            if oi24 >= P["oiStijging"] and k24 >= P["oiKoersStijging"]:
                hits.append(("futures", f"hefboominzet +{oi24*100:.0f}% en koers +{k24*100:.0f}% in 24 uur"))
        return hits

    def toets(c, potje):
        """True = kopen mag. Houdt bij welke remmen ingrepen of in schaduw zouden ingrijpen."""
        closes = [x[1] for x in state["prices"].get(c, [])]
        hits = filters(c, potje, closes)
        fs = state.setdefault("filterStats", {})
        harde = [(n, r) for n, r in hits if P[{"nieuws": "filterNieuws", "fg": "filterFG", "futures": "filterFutures"}[n]] == "aan"]
        for n, _ in hits:
            d = fs.setdefault(n, {"geblokkeerd": 0, "schaduw": 0})
            d["geblokkeerd" if harde else "schaduw"] += 1
        if harde:
            msgs.append(f"Aankoop {naam(c)} ({POTNAAM[potje]}) tegengehouden: " + "; ".join(r for _, r in harde) + ".")
            return False, []
        return True, [n for n, _ in hits]

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

    def trade(c, side, qty, price, potje, reason, pos=None, tags=None):
        kostpct = P["kosten"] + spreads.get(c, 0) / 2
        bruto = qty * price; kost = bruto * kostpct
        state["stats"]["kosten"] += kost
        rec = {"id": f"{now}-{c}-{side}", "t": now, "coin": c, "naam": naam(c), "potje": potje, "side": side,
               "prijs": float(f"{price:.6g}"), "aantal": qty, "bedrag": round(bruto, 2), "kosten": round(kost, 2), "reden": reason}
        if tags: rec["filters"] = tags
        if pos and pos.get("filters"): rec["filters"] = pos["filters"]
        if side == "koop":
            state["cash"] -= bruto + kost
        else:
            state["cash"] += bruto - kost
            pnl = bruto - kost - pos["inleg"]
            rec["resultaat"] = round(pnl, 2)
            state["stats"]["gesloten"] += 1
            state["stats"]["winst" if pnl > 0 else "verlies"] += 1
            sp = state.setdefault("statsPot", {}).setdefault(potje, {"gesloten": 0, "winst": 0, "resultaat": 0.0})
            sp["gesloten"] += 1; sp["winst"] += pnl > 0; sp["resultaat"] = round(sp["resultaat"] + pnl, 2)
            for fnaam in pos.get("filters") or []:   # wat had deze rem opgeleverd? (negatief resultaat = rem had geld bespaard)
                d = state.setdefault("filterStats", {}).setdefault(fnaam, {"geblokkeerd": 0, "schaduw": 0})
                d["schaduwResultaat"] = round(d.get("schaduwResultaat", 0) + pnl, 2); d["schaduwGesloten"] = d.get("schaduwGesloten", 0) + 1
        state["trades"].append(rec); del state["trades"][:-P["maxTrades"]]
        return rec, kostpct

    # 5. Posities beheren, daarna kansen verzamelen
    kansen, momkansen, trend_cnt, inloop, geblokt = [], [], 0, 0, 0
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
            if pos["potje"] == "momentum":
                dagen = (now - pos["entryT"]) / 86400
                if p <= pos["entry"] * (1 - P["momStop"]):
                    reden = f"Stop: uitbraak mislukt, koers {int(P['momStop']*100)}% onder de instapprijs."
                elif p <= pos["piek"] * (1 - P["momTrailing"]):
                    reden = f"Winst/verlies vastgezet: koers {int(P['momTrailing']*100)}% onder het hoogste punt sinds aankoop."
                elif dagen >= P["momMaxDagen"]:
                    reden = f"Na {P['momMaxDagen']} dagen gesloten; de uitbraak is uitgewerkt."
            elif pos["potje"] == "trend":
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
        vs = state.get("vols", {}).get(c, [])
        if len(vs) >= 43 and len(closes) >= 43:
            gem = sum(vs[-43:-1]) / 42
            if gem > 0 and vs[-1] >= P["momVolFactor"] * gem and p > max(closes[-43:-1]):
                momkansen.append((-vs[-1] / gem, c, f"Uitbraak: koers boven het weekhoogste en {vs[-1]/gem:.1f}x zoveel handel als normaal."))
        if trend_up and closes[-2] <= e_k[-2] and p > e_k[-1]:
            kansen.append((0, -(p / e_l[-1] - 1), c, "trend", "Trend omhoog en de koers veert net weer boven het korte gemiddelde uit."))
        elif r[-1] < P["veerInstapRsi"]:
            kansen.append((1, r[-1], c, "terugveer", "Scherpe daling: de koers is ongewoon laag gezakt, kans op terugvering."))

    # 6. Sterkste kansen kopen zolang er plek en geld is
    kansen.sort()
    overgeslagen = 0
    for _, _, c, potje, uitleg in kansen:
        if state.get("paused") or sum(x["potje"] != "momentum" for x in state["positions"]) >= P["maxPosities"]:
            overgeslagen += 1; continue
        kp = P["kosten"] + spreads.get(c, 0) / 2
        budget = min(state["cash"] / (1 + kp), equity() / (P["maxPosities"] + P["momMaxPosities"]))
        if budget < 25:
            overgeslagen += 1; continue
        ok, tags = toets(c, potje)
        if not ok: continue
        p = last[c]
        rec, _ = trade(c, "koop", budget / p, p, potje, uitleg, tags=tags)
        state["positions"].append({"coin": c, "potje": potje, "qty": budget / p, "entry": p, "entryT": now,
                                   "piek": p, "inleg": round(budget * (1 + kp), 2), "filters": tags})
        msgs.append(f"GEKOCHT {naam(c)} voor {eur(rec['bedrag'])} ({POTNAAM[potje]}). {uitleg}")
    momkansen.sort()
    for _, c, uitleg in momkansen:
        if c in {x["coin"] for x in state["positions"]}: continue
        if state.get("paused") or sum(x["potje"] == "momentum" for x in state["positions"]) >= P["momMaxPosities"]:
            overgeslagen += 1; continue
        kp = P["kosten"] + spreads.get(c, 0) / 2
        budget = min(state["cash"] / (1 + kp), P["momBudget"])
        if budget < 25:
            overgeslagen += 1; continue
        ok, tags = toets(c, "momentum")
        if not ok: continue
        p = last[c]
        rec, _ = trade(c, "koop", budget / p, p, "momentum", uitleg, tags=tags)
        state["positions"].append({"coin": c, "potje": "momentum", "qty": budget / p, "entry": p, "entryT": now,
                                   "piek": p, "inleg": round(budget * (1 + kp), 2), "filters": tags})
        msgs.append(f"GEKOCHT {naam(c)} voor {eur(rec['bedrag'])} (momentum-uitbraak). {uitleg}")

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
    state["filterModus"] = {"nieuws": P["filterNieuws"], "fg": P["filterFG"], "futures": P["filterFutures"]}
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
    ap.add_argument("--fng", help="ruwe JSON van api.alternative.me/fng (optioneel)")
    ap.add_argument("--news", help="JSON-lijst [{titel, t, bron}] met nieuwskoppen (optioneel)")
    a = ap.parse_args()
    state = json.load(open(a.state))
    now = a.now or int(time.time())
    P = {**DEFAULT_PARAMS, **state.get("params", {})}
    tick, fx, notes = parse_tickers(open(a.tickers).read(), now, P["maxOuderdom"])
    fng = parse_fng(open(a.fng).read()) if a.fng else None
    news = json.load(open(a.news)) if a.news else None
    state, msgs = run(state, tick, now, notes, fng=fng, news=news)
    json.dump(state, open(a.out, "w"), separators=(",", ":"))
    print(f"Check {tijd(now)} — waarde {eur(state['equity'][-1][1])} (1 USD = €{fx:.4f})")
    for m in msgs: print("-", m)
