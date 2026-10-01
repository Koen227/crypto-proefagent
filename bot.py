#!/usr/bin/env python3
"""Crypto Proefagent – papieren handel op Bitvavo-koersen (in euro's).

GitHub draait run.py elke 15 minuten:
- elke 15 minuten BEWAKEN: stopverliezen, winst vastzetten, nieuwsrem bijwerken;
- elke 4 uur SCANNEN: alle Bitvavo-markten bekijken en nieuwe kansen zoeken.
Er wordt nergens echt gehandeld: dit is papieren handel met fictief geld.

Welke munten mogen meedoen bepaalt het script zelf:
- alleen euromarkten op Bitvavo, zonder stablecoins, verpakte varianten, memecoins of ingestorte projecten;
- minstens 7 dagen koersgeschiedenis;
- elke aankoop moet zijn kosten waard zijn: de verwachte beweging moet minstens 3x de totale kosten zijn
  (transactiekosten + bied-laatverschil + wegloop in het orderboek, voor kopen en verkopen);
- de positie mag hooguit 2% zijn van wat er per dag in die munt omgaat, zodat de agent er ook weer uit kan;
- niet kopen na een crash, bij slecht nieuws of (in schaduwmodus) bij extreme hebzucht of veel hefboom.
"""
import argparse, json, math, re, time, datetime as dt

NAMES = {"BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "XRP": "XRP", "ADA": "Cardano",
         "LINK": "Chainlink", "AVAX": "Avalanche", "DOT": "Polkadot", "LTC": "Litecoin",
         "QNT": "Quant", "CRO": "Cronos", "NEAR": "NEAR", "HBAR": "Hedera", "AAVE": "Aave",
         "SUI": "Sui", "ARB": "Arbitrum", "XLM": "Stellar", "WLD": "Worldcoin", "MOVR": "Moonriver",
         "FIL": "Filecoin", "FET": "Fetch.ai", "ICP": "Internet Computer", "ARK": "Ark",
         "ENA": "Ethena", "GALA": "Gala", "BCH": "Bitcoin Cash", "ONDO": "Ondo", "VIRTUAL": "Virtuals",
         "TAO": "Bittensor", "UNI": "Uniswap", "W": "Wormhole", "ATOM": "Cosmos", "STX": "Stacks",
         "JASMY": "JasmyCoin", "INJ": "Injective", "LDO": "Lido", "VET": "VeChain", "POL": "Polygon",
         "JUP": "Jupiter", "APT": "Aptos", "ALGO": "Algorand", "HYPE": "Hyperliquid", "OP": "Optimism",
         "PYTH": "Pyth", "FLR": "Flare", "AR": "Arweave", "RENDER": "Render", "ETC": "Ethereum Classic",
         "IMX": "Immutable", "GRT": "The Graph", "CRV": "Curve", "TRX": "TRON", "TON": "Toncoin",
         "SEI": "Sei", "TIA": "Celestia", "KAS": "Kaspa", "XTZ": "Tezos", "EGLD": "MultiversX",
         "SAND": "The Sandbox", "MANA": "Decentraland", "AXS": "Axie Infinity", "CHZ": "Chiliz",
         "MKR": "Maker", "SNX": "Synthetix", "COMP": "Compound", "1INCH": "1inch", "ENS": "ENS",
         "KSM": "Kusama", "ZEC": "Zcash", "XMR": "Monero", "EOS": "EOS", "NEO": "NEO", "IOTA": "IOTA",
         "THETA": "Theta", "ROSE": "Oasis", "MINA": "Mina", "QTUM": "Qtum", "ZIL": "Zilliqa",
         "BNB": "BNB", "STRK": "Starknet", "PENDLE": "Pendle", "JTO": "Jito", "RUNE": "THORChain"}

EXCLUDE = {
    # stablecoins, euro/dollar-tokens en goud: bewegen (bijna) niet
    "USDT", "USDC", "DAI", "FDUSD", "TUSD", "PYUSD", "USDE", "USDS", "USD1", "RLUSD", "EURC", "EURQ",
    "EURCV", "EURR", "EURI", "USDG", "BUSD", "USDP", "GUSD", "FRAX", "PAXG", "XAUT", "USDQ",
    # verpakte en gestakete varianten van andere munten
    "WBTC", "WETH", "CBBTC", "STETH", "WSTETH", "CBETH", "JITOSOL", "MSOL", "BNSOL", "LBTC", "RETH",
    # memecoins
    "DOGE", "SHIB", "PEPE", "BONK", "WIF", "FLOKI", "TRUMP", "FARTCOIN", "PENGU", "CASHCAT", "BASECAT",
    "ELON", "TURBO", "WEN", "COQ", "POPCAT", "MEW", "BRETT", "MOG", "GOAT", "SPX", "NEIRO", "PNUT",
    "MOODENG", "USELESS", "GOATED", "CAW", "DOG", "BOME", "MEME", "BABYDOGE", "MELANIA", "PUMP", "BAN",
    "CHILLGUY", "GIGA", "ACT", "FWOG", "SLERF", "LADYS", "DOGS", "NOT", "SUNDOG", "BABY", "MYRO", "WOJAK",
    "PONKE", "MICHI", "SPX6900", "APU", "TOSHI", "KEKIUS", "AI16Z", "GRIFFAIN", "ZEREBRO", "LUCE",
    # ingestorte projecten
    "LUNC", "USTC", "LUNA", "FTT",
}

DEFAULT_PARAMS = {
    "startKapitaal": 1000.0,
    "kosten": 0.0025,          # 0,25% Bitvavo-transactiekosten (taker), per aankoop en per verkoop
    "kostenMarge": 3.0,        # verwachte beweging moet minstens 3x de totale kosten zijn
    "maxAandeelVolume": 0.02,  # positie hooguit 2% van de 24-uurs handel in die munt
    "maxSpread": 0.02,         # harde grens: niet kopen bij een bied-laatverschil boven 2%
    "minBeweeglijkheid": 0.002,# munten die (bijna) niet bewegen (stablecoins) overslaan
    "volInstap": 25000.0,      # min. 24-uurs handel (EUR) om gevolgd te worden
    "volBlijf": 10000.0,       # min. 24-uurs handel (EUR) om gevolgd te blijven
    "maxNieuwPerRun": 80,      # zoveel nieuwe munten per run van geschiedenis voorzien
    "crashGrens": 0.40,        # niet kopen als koers >40% onder het weekhoogste staat
    "maxPosities": 4,
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
    "filterNieuws": "aan", "filterFG": "schaduw", "filterFutures": "schaduw",
    "fgHebzucht": 80,
    "oiStijging": 0.25, "oiKoersStijging": 0.10,
    "nieuwsUren": 48,
    "maxSprong": 0.25,
    "maxOuderdom": 1800,
    "scanInterval": 14400,     # elke 4 uur kansen zoeken
    "maxPunten": 60, "maxEquity": 1500, "maxTrades": 400, "maxLog": 200,
}

POTNAAM = {"trend": "trendvolgen", "terugveer": "terugveren", "momentum": "momentum-uitbraak"}
NEGATIEF = ("hack", "hacked", "exploit", "drained", "stolen", "delist", "lawsuit", "sued", "charges",
            "fraud", "rug pull", "rugpull", "insolven", "bankrupt", "halts withdrawals", "suspends withdrawals",
            "pauses withdrawals", "security incident", "vulnerability", "attack", "scam", "ponzi", "investigation")
FILTERPARAM = {"nieuws": "filterNieuws", "fg": "filterFG", "futures": "filterFutures"}


def eur(v):
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("-" if v < 0 else "") + "€" + s


def naam(c): return NAMES.get(c, c)


def noemt_munt(titel, c):
    if len(c) >= 3 and re.search(rf"(?<![A-Za-z0-9$]){re.escape(c)}(?![A-Za-z0-9])", titel):
        return True
    n = NAMES.get(c)
    return bool(n and len(n) >= 3 and n != c and re.search(rf"\b{re.escape(n)}\b", titel))


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


def beweeglijkheid(closes, n=42):
    """Standaardafwijking van de 4-uursrendementen (log) over de laatste n perioden."""
    c = [x for x in closes[-(n + 1):] if x > 0]
    if len(c) < 10: return None
    r = [math.log(c[i] / c[i - 1]) for i in range(1, len(c))]
    m = sum(r) / len(r)
    return math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1))


def _f(x):
    try: return float(x)
    except (TypeError, ValueError): return 0.0


def parse_bitvavo(rows, now, max_age):
    """Bitvavo /v2/ticker/24h -> {munt: {prijs, spread, vol (EUR)}} voor alle euromarkten."""
    out, oud = {}, 0
    for r in rows or []:
        m = r.get("market") or ""
        if not m.endswith("-EUR"): continue
        base = m[:-4]
        last = _f(r.get("last"))
        if last <= 0 or not base.replace("1", "").isalnum(): continue
        t = r.get("timestamp")
        if t and abs(now - t / 1000) > max_age: oud += 1; continue
        bid, ask = _f(r.get("bid")), _f(r.get("ask"))
        spread = (ask - bid) / ((ask + bid) / 2) if bid > 0 and ask > bid else 0.0
        out[base] = {"prijs": last, "spread": spread, "vol": _f(r.get("volumeQuote"))}
    if "BTC" not in out:
        raise ValueError("Geen bruikbare Bitvavo-koers voor Bitcoin; check overgeslagen.")
    notes = [f"{oud} koersen waren ouder dan 30 minuten en zijn niet gebruikt."] if oud > 50 else []
    return out, notes


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


def wegloop(boek, bedrag, kant="asks"):
    """Gemiddelde prijsafwijking t.o.v. de beste prijs bij een order van `bedrag` euro."""
    rijen = (boek or {}).get(kant) or []
    if not rijen: return None
    beste = _f(rijen[0][0]); rest, kosten, stuks = bedrag, 0.0, 0.0
    for prijs, aantal in rijen:
        p, a = _f(prijs), _f(aantal)
        neem = min(rest, p * a)
        kosten += neem; stuks += neem / p; rest -= neem
        if rest <= 1e-9: break
    if rest > 1e-9: return 1.0  # boek te dun: behandel als onbetaalbaar
    gem = kosten / stuks
    return abs(gem / beste - 1)


def run(state, tick, now, notes=(), fng=None, news=None, boek=None, historie=None, oi=None, scan=None):
    """Eén check. Geeft (state, meldingen, gewijzigd) terug.

    boek(c)     -> {"bids": [[prijs, aantal]...], "asks": [...]} of None   (orderboek, optioneel)
    historie(c) -> [[t_sluiting, slotkoers, handel_EUR_4u], ...] oud->nieuw (4-uurskaarsen, optioneel)
    oi          -> {munt: open interest} uit perpetual futures (optioneel)
    """
    msgs = list(notes)
    oud_p = state.get("params", {})
    if state.get("bron") != "bitvavo":
        # overstap: koersreeksen opnieuw opbouwen uit Bitvavo-geschiedenis, oude USD-parameters vervallen
        state["params"] = {"startKapitaal": oud_p.get("startKapitaal", 1000.0)}
        state["bron"] = "bitvavo"
        state["prices"], state["vols"], state["oi"], state["universe"] = {}, {}, {}, {}
        state["lastScan"] = 0
        msgs.append("Overgestapt op Bitvavo-koersen: de agent scant nu alle euromarkten van Bitvavo.")
    P = {**DEFAULT_PARAMS, **state.get("params", {})}
    state["params"] = P
    for k, v in (("cash", P["startKapitaal"]), ("positions", []), ("trades", []), ("log", []),
                 ("equity", []), ("prices", {}), ("vols", {}), ("universe", {}),
                 ("stats", {"kosten": 0.0, "gesloten": 0, "winst": 0, "verlies": 0})):
        state.setdefault(k, v)
    U = state["universe"]
    held = {x["coin"] for x in state["positions"]}
    bench = set((state.get("start") or {}).get("mandje", {}).keys())
    if scan is None:
        scan = now // P["scanInterval"] > state.get("lastScan", 0) // P["scanInterval"]
    gewijzigd = bool(msgs)

    def koers(c):
        t = tick.get(c)
        if t: return t["prijs"]
        s = state["prices"].get(c) or []
        return s[-1][1] if s else None

    def equity():
        return state["cash"] + sum(x["qty"] * (koers(x["coin"]) or x["entry"]) for x in state["positions"])

    # --- Signalen (in elke check) ---------------------------------------------------------------
    if fng is not None and fng != state.get("fng"):
        state["fng"] = fng
    alarm = state.setdefault("nieuwsAlarm", {})
    for c in list(alarm):
        if alarm[c]["tot"] < now: del alarm[c]; gewijzigd = True
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
            rem = [c for c in munten if c not in ("BTC", "ETH")] if neg else []
            lijst.append({"t": t_it, "titel": titel, "bron": it.get("bron", ""), "munten": munten, "negatief": neg, "rem": rem})
            gewijzigd = True
            for c in rem:
                alarm[c] = {"tot": t_it + P["nieuwsUren"] * 3600, "titel": titel}
                if c in held:
                    msgs.append(f"Let op: slecht nieuws over {naam(c)}, dat de agent bezit: \"{titel}\".")
        del lijst[:-20]
        state["nieuwsGezien"] = list(gezien)[-150:]

    # --- Weekbewaking ----------------------------------------------------------------------------
    ws = week_start(now)
    if state.get("week", {}).get("start") != ws:
        state["week"] = {"start": ws, "equity": equity()}; gewijzigd = True
        if state.get("paused"):
            state["paused"] = False
            msgs.append("Nieuwe week: pauze opgeheven, de agent mag weer kopen.")
    if not state.get("paused") and equity() < state["week"]["equity"] * (1 - P["weekVerliesStop"]):
        state["paused"] = True
        msgs.append(f"Weekverlies groter dan {int(P['weekVerliesStop']*100)}%: geen nieuwe aankopen tot maandag. Verkopen blijven mogelijk.")

    def trade(c, side, qty, price, potje, reason, pos=None, tags=None, slip=0.0):
        sp = tick.get(c, {}).get("spread", 0)
        kostpct = P["kosten"] + sp / 2 + slip
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
            spt = state.setdefault("statsPot", {}).setdefault(potje, {"gesloten": 0, "winst": 0, "resultaat": 0.0})
            spt["gesloten"] += 1; spt["winst"] += pnl > 0; spt["resultaat"] = round(spt["resultaat"] + pnl, 2)
            for fnaam in pos.get("filters") or []:
                d = state.setdefault("filterStats", {}).setdefault(fnaam, {"geblokkeerd": 0, "schaduw": 0})
                d["schaduwResultaat"] = round(d.get("schaduwResultaat", 0) + pnl, 2)
                d["schaduwGesloten"] = d.get("schaduwGesloten", 0) + 1
        state["trades"].append(rec); del state["trades"][:-P["maxTrades"]]
        return rec

    def verkoop_check(pos, p, closes=None):
        """Verkoopregels. Zonder `closes` (bewaakmodus) alleen de prijsregels."""
        pos["piek"] = max(pos.get("piek", pos["entry"]), p)
        pos["nu"] = float(f"{p:.6g}")
        dagen = (now - pos["entryT"]) / 86400
        ready = closes is not None and len(closes) >= P["emaLang"] + 1
        if pos["potje"] == "momentum":
            if p <= pos["entry"] * (1 - P["momStop"]):
                return f"Stop: uitbraak mislukt, koers {int(P['momStop']*100)}% onder de instapprijs."
            if p <= pos["piek"] * (1 - P["momTrailing"]):
                return f"Winst/verlies vastgezet: koers {int(P['momTrailing']*100)}% onder het hoogste punt sinds aankoop."
            if dagen >= P["momMaxDagen"]:
                return f"Na {P['momMaxDagen']} dagen gesloten; de uitbraak is uitgewerkt."
        elif pos["potje"] == "trend":
            if p <= pos["entry"] * (1 - P["trendStop"]):
                return f"Stop: koers meer dan {int(P['trendStop']*100)}% onder de instapprijs gezakt."
            if p <= pos["piek"] * (1 - P["trendTrailing"]):
                return f"Winst/verlies vastgezet: koers {int(P['trendTrailing']*100)}% onder het hoogste punt sinds aankoop."
            if ready:
                e_k = ema(closes, P["emaKort"]); e_l = ema(closes, P["emaLang"])
                if e_k[-1] < e_l[-1] or p < e_l[-1]:
                    return "Trend voorbij: de koers zakte onder het lange gemiddelde."
        else:
            if p >= pos["entry"] * (1 + P["veerWinst"]):
                return f"Winstdoel gehaald: {int(P['veerWinst']*100)}% boven de instapprijs."
            if p <= pos["entry"] * (1 - P["veerStop"]):
                return f"Stop: koers verder gezakt dan {int(P['veerStop']*100)}% onder de instapprijs."
            if ready:
                r = rsi(closes, P["rsiPeriode"])
                if r[-1] >= P["veerUitstapRsi"]:
                    return "Terugvering voltooid: de koers is hersteld naar een normaal niveau."
            if dagen >= P["veerMaxDagen"]:
                return f"Te lang vastgehouden (meer dan {P['veerMaxDagen']} dagen) zonder herstel."
        return None

    def verkoop(pos, p, reden):
        rec = trade(pos["coin"], "verkoop", pos["qty"], p, pos["potje"], reden, pos)
        state["positions"].remove(pos)
        if reden.startswith("Stop"):
            state.setdefault("cooldown", {})[pos["coin"]] = now + 86400
        msgs.append(f"VERKOCHT {naam(pos['coin'])} voor {eur(rec['bedrag'])}, resultaat {eur(rec['resultaat'])}. {reden}")

    # --- BEWAKEN (elke 15 minuten): alleen prijsregels voor bezit --------------------------------
    if not scan:
        for pos in list(state["positions"]):
            p = koers(pos["coin"]) if pos["coin"] in tick else None
            if p is None: continue
            oude_piek = pos.get("piek")
            reden = verkoop_check(pos, p)
            if reden:
                verkoop(pos, p, reden); gewijzigd = True
            elif pos.get("piek") != oude_piek:
                gewijzigd = True
        if any(m.startswith("VERKOCHT") for m in msgs):
            state["equity"].append([now, round(equity(), 2), state["equity"][-1][2] if state["equity"] else None])
        for m in msgs:
            state["log"].append({"t": now, "msg": m})
        del state["log"][:-P["maxLog"]]
        state["lastCheck"] = now
        return state, msgs, gewijzigd

    # --- SCANNEN (elke 4 uur) --------------------------------------------------------------------
    # 1. Universum: alle euromarkten met genoeg handel, zonder uitgesloten soorten
    nieuw, weg = [], []
    for c, t in tick.items():
        if c in EXCLUDE or c in U: continue
        if t["vol"] >= P["volInstap"]:
            U[c] = {"since": now}; nieuw.append(c)
    for c in list(U):
        t = tick.get(c)
        if c in EXCLUDE or t is None or t["vol"] < P["volBlijf"]:
            if c not in held: weg.append(naam(c))
            del U[c]
    for c in U: U[c]["vol"] = round(tick.get(c, {}).get("vol", 0))
    if weg: msgs.append(f"{len(weg)} munt(en) niet meer gevolgd wegens te weinig handel: " + ", ".join(sorted(weg)[:12]) + ("…" if len(weg) > 12 else "") + ".")

    volg = set(U) | held | bench
    # 2. Geschiedenis aanvullen voor munten zonder koersreeks (via Bitvavo-kaarsen)
    aangevuld = 0
    if historie:
        zonder = sorted((c for c in volg if len(state["prices"].get(c) or []) < P["emaLang"] + 1 and not U.get(c, {}).get("histTry")),
                        key=lambda c: -tick.get(c, {}).get("vol", 0))
        for c in zonder[:P["maxNieuwPerRun"]]:
            if c in U: U[c]["histTry"] = now
            try:
                h = historie(c) or []
            except Exception:
                h = []
            h = [x for x in h if x[0] <= now]
            if len(h) < 8: continue
            state["prices"][c] = [[int(x[0]), float(f"{x[1]:.6g}")] for x in h][-P["maxPunten"]:]
            v4 = [x[2] for x in h]
            state["vols"][c] = [round(sum(v4[max(0, i - 5):i + 1])) for i in range(5, len(v4))][-P["maxPunten"]:]
            aangevuld += 1
    if nieuw:
        msgs.append(f"{len(nieuw)} munt(en) nieuw gevolgd" + (f", waarvan {aangevuld} met koersgeschiedenis van Bitvavo" if aangevuld else "") + ".")

    # 3. Koersen toevoegen
    last, spreads = {}, {}
    for c in volg:
        t = tick.get(c)
        series = state["prices"].setdefault(c, [])
        if not t: continue
        p = t["prijs"]
        if series and abs(p / series[-1][1] - 1) > P["maxSprong"] * (1 + (now - series[-1][0]) / 86400):
            msgs.append(f"{naam(c)}: koers wijkt te sterk af van de vorige; genegeerd als mogelijke datafout.")
            continue
        if not series or now - series[-1][0] > 3600:
            series.append([now, float(f"{p:.6g}")]); del series[:-P["maxPunten"]]
            vs = state["vols"].setdefault(c, []); vs.append(round(t["vol"])); del vs[:-P["maxPunten"]]
        last[c] = p; spreads[c] = t["spread"]
        if oi and oi.get(c):
            o = state.setdefault("oi", {}).setdefault(c, []); o.append(float(f"{oi[c]:.6g}")); del o[:-P["maxPunten"]]
    for k in ("prices", "vols", "oi"):
        for c in list(state.get(k, {})):
            if c not in volg: del state[k][c]

    # 4. Startpunt en vergelijkingsmandje (alleen bij een nieuwe proef)
    if not state.get("start"):
        top = [c for c in ("BTC", "ETH", "SOL", "XRP", "ADA", "LINK", "AVAX", "DOT", "LTC") if c in last]
        per = P["startKapitaal"] * (1 - P["kosten"]) / len(top)
        state["start"] = {"t": now, "equity": P["startKapitaal"], "mandje": {c: per / last[c] for c in top}}
        msgs.append(f"Proef gestart met {eur(P['startKapitaal'])} fictief geld.")

    # 5. Remmen
    def filters(c, potje, closes):
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
        closes = [x[1] for x in state["prices"].get(c, [])]
        hits = filters(c, potje, closes)
        fs = state.setdefault("filterStats", {})
        harde = [(n, r) for n, r in hits if P[FILTERPARAM[n]] == "aan"]
        for n, _ in hits:
            d = fs.setdefault(n, {"geblokkeerd": 0, "schaduw": 0})
            d["geblokkeerd" if harde else "schaduw"] += 1
        if harde:
            msgs.append(f"Aankoop {naam(c)} ({POTNAAM[potje]}) tegengehouden: " + "; ".join(r for _, r in harde) + ".")
            return False, []
        return True, [n for n, _ in hits]

    # 6. Bezit beheren, daarna kansen verzamelen
    kansen, trend_cnt, kort, geblokt, actief = [], 0, 0, 0, 0
    for c in sorted(volg):
        if c not in last: continue
        closes = [x[1] for x in state["prices"][c]]
        p = closes[-1]
        pos = next((x for x in state["positions"] if x["coin"] == c), None)
        if pos:
            reden = verkoop_check(pos, p, closes)
            if c not in U and not reden:
                reden = "Munt valt buiten de selectie (te weinig handel); positie gesloten."
            if reden: verkoop(pos, p, reden)
            continue
        if c not in U: continue
        if len(closes) < P["emaLang"] + 1:
            kort += 1; continue
        sigma = beweeglijkheid(closes)
        if sigma is None or sigma < P["minBeweeglijkheid"]: continue
        actief += 1
        e_k = ema(closes, P["emaKort"]); e_l = ema(closes, P["emaLang"]); r = rsi(closes, P["rsiPeriode"])
        trend_up = e_k[-1] > e_l[-1] and p > e_l[-1]
        trend_cnt += trend_up
        if now < state.get("cooldown", {}).get(c, 0): continue
        if spreads.get(c, 0) > P["maxSpread"] or p < max(closes[-42:]) * (1 - P["crashGrens"]):
            geblokt += 1; continue
        horizon = sigma * math.sqrt(18)   # verwachte beweging over ~3 dagen
        vs = state["vols"].get(c, [])
        if len(vs) >= 43 and len(closes) >= 43:
            gem = sum(vs[-43:-1]) / 42
            if gem > 0 and vs[-1] >= P["momVolFactor"] * gem and p > max(closes[-43:-1]):
                ratio = vs[-1] / gem
                kansen.append(("momentum", -ratio, c, horizon * min(ratio / P["momVolFactor"], 2.0),
                               f"Uitbraak: koers boven het weekhoogste en {ratio:.1f}x zoveel handel als normaal."))
        if trend_up and closes[-2] <= e_k[-2] and p > e_k[-1]:
            kansen.append(("trend", -(p / e_l[-1] - 1), c, horizon,
                           "Trend omhoog en de koers veert net weer boven het korte gemiddelde uit."))
        elif r[-1] < P["veerInstapRsi"]:
            kansen.append(("terugveer", r[-1], c, min(P["veerWinst"], horizon),
                           "Scherpe daling: de koers is ongewoon laag gezakt, kans op terugvering."))

    # 7. Kosten-batenafweging en kopen
    volgorde = {"trend": 0, "terugveer": 1, "momentum": 2}
    kansen.sort(key=lambda k: (volgorde[k[0]], k[1]))
    overgeslagen, te_duur = 0, 0
    for potje, _, c, verwacht, uitleg in kansen:
        if c in {x["coin"] for x in state["positions"]}: continue
        if potje == "momentum":
            vol_ = sum(x["potje"] == "momentum" for x in state["positions"]) >= P["momMaxPosities"]
            budget = min(state["cash"], P["momBudget"])
        else:
            vol_ = sum(x["potje"] != "momentum" for x in state["positions"]) >= P["maxPosities"]
            budget = min(state["cash"], equity() / (P["maxPosities"] + P["momMaxPosities"]))
        if state.get("paused") or vol_:
            overgeslagen += 1; continue
        budget = min(budget, P["maxAandeelVolume"] * tick[c]["vol"])
        if budget < 25:
            overgeslagen += 1; continue
        slip = 0.0
        if boek:
            try: b = boek(c)
            except Exception: b = None
            w_k, w_v = wegloop(b, budget, "asks"), wegloop(b, budget, "bids")
            if w_k is not None and w_v is not None: slip = (w_k + w_v) / 2
        kosten_rt = 2 * P["kosten"] + spreads.get(c, 0) + 2 * slip
        if verwacht < P["kostenMarge"] * kosten_rt:
            te_duur += 1; continue
        ok, tags = toets(c, potje)
        if not ok: continue
        budget = budget / (1 + P["kosten"] + spreads.get(c, 0) / 2 + slip)
        p = last[c] * (1 + slip)
        rec = trade(c, "koop", budget / p, p, potje, uitleg, tags=tags, slip=0.0)
        state["positions"].append({"coin": c, "potje": potje, "qty": budget / p, "entry": p, "entryT": now,
                                   "piek": p, "inleg": round(rec["bedrag"] + rec["kosten"], 2), "filters": tags})
        msgs.append(f"GEKOCHT {naam(c)} voor {eur(rec['bedrag'])} ({POTNAAM[potje]}). {uitleg} "
                    f"Verwachte beweging {verwacht*100:.1f}% tegen {kosten_rt*100:.2f}% kosten.")

    # 8. Stand bijwerken
    eq = equity()
    mandje = None
    if state.get("start"):
        mandje = sum(q * (koers(c) or 0) for c, q in state["start"]["mandje"].items())
    state["equity"].append([now, round(eq, 2), round(mandje, 2) if mandje else None])
    del state["equity"][:-P["maxEquity"]]
    state["universeInfo"] = {"totaal": len(U), "inloop": kort, "actief": actief, "trend": trend_cnt,
                             "markten": len(tick), "teDuur": te_duur}
    state["names"] = {c: naam(c) for c in held | bench | {x["coin"] for x in state["trades"][-50:]}}
    state["filterModus"] = {"nieuws": P["filterNieuws"], "fg": P["filterFG"], "futures": P["filterFutures"]}
    if not any(m.startswith(("GEKOCHT", "VERKOCHT")) for m in msgs):
        delen = [f"{len(state['positions'])} posities vastgehouden" if state["positions"] else "geen posities",
                 f"{len(tick)} markten gescand, {len(U)} met genoeg handel" + (f" ({kort} nog te kort genoteerd)" if kort else ""),
                 f"{trend_cnt} van {actief} in een stijgende trend"]
        if te_duur: delen.append(f"{te_duur} kans(en) niet de kosten waard")
        if geblokt: delen.append(f"{geblokt} geblokkeerd (te groot prijsverschil of recente crash)")
        if overgeslagen: delen.append(f"{overgeslagen} kans(en) overgeslagen (vol, gepauzeerd of te weinig saldo)")
        msgs.append("Geen transactie: " + "; ".join(delen) + ".")
    for m in msgs:
        state["log"].append({"t": now, "msg": m})
    del state["log"][:-P["maxLog"]]
    state["lastRun"] = state["lastScan"] = state["lastCheck"] = now
    state["runs"] = state.get("runs", 0) + 1
    return state, msgs, True


def samenvatting(state):
    """Klein bestand voor het dashboard (de volledige stand blijft in data/state.json)."""
    keys = ("cash", "positions", "trades", "log", "equity", "stats", "statsPot", "filterStats", "filterModus",
            "fng", "nieuws", "nieuwsAlarm", "universeInfo", "names", "start", "paused", "lastRun", "lastScan",
            "lastCheck", "runs", "params", "bron")
    s = {k: state.get(k) for k in keys if k in state}
    s["trades"] = (state.get("trades") or [])[-150:]
    s["log"] = (state.get("log") or [])[-80:]
    pp = state.get("params") or {}
    s["params"] = {"startKapitaal": pp.get("startKapitaal", 1000.0), "scanInterval": pp.get("scanInterval", 14400)}
    held = {x["coin"] for x in state.get("positions", [])}
    s["prices"] = {c: (state["prices"].get(c) or [])[-1:] for c in held if c in state.get("prices", {})}
    for x in s.get("positions") or []:
        if x.get("nu"): s["prices"][x["coin"]] = [[state.get("lastCheck"), x["nu"]]]
    s["oiAantal"] = len(state.get("oi", {}))
    return s


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Eén check met een opgeslagen Bitvavo-tickerbestand (voor testen).")
    ap.add_argument("--state", required=True); ap.add_argument("--tickers", required=True)
    ap.add_argument("--out", required=True); ap.add_argument("--now", type=int)
    ap.add_argument("--scan", action="store_true", help="forceer een volledige scan")
    a = ap.parse_args()
    state = json.load(open(a.state))
    now = a.now or int(time.time())
    tick, notes = parse_bitvavo(json.load(open(a.tickers)), now, DEFAULT_PARAMS["maxOuderdom"])
    state, msgs, _ = run(state, tick, now, notes, scan=True if a.scan else None)
    json.dump(state, open(a.out, "w"), separators=(",", ":"))
    for m in msgs: print("-", m)
