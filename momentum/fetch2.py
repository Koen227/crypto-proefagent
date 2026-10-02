"""Kandidaten voor uitbreiding: UCITS-ETF's (kopen vanuit NL) + Amerikaanse 'proxy' met langere historie (alleen voor backtest)."""
import os, time
import yfinance as yf
KANDIDATEN = [
    # India / China / andere opkomende markten
    "XCS5.DE", "NDIA.L", "QDV5.DE", "XCS6.DE", "ICGA.DE", "IBZL.L", "4BRZ.DE", "IKOR.L", "CSKR.L", "ITWN.L", "XMLA.DE", "LTAM.L",
    "INDA", "MCHI", "EWZ", "EWY", "EWT", "ILF",
    # kernenergie / uranium
    "NUKL.DE", "URNU.DE", "U3O8.DE", "NLR", "URA",
    # energie (wereld), olie & gas, schone energie
    "SPYN.DE", "IQQE.DE", "IQQH.DE", "INRG.L", "XLE", "ICLN",
    # zilver, grondstoffen, goudmijnen, vastgoed
    "PHAG.L", "XAD6.DE", "EXXY.DE", "CMOD.L", "G2X.DE", "IQQ6.DE", "SLV", "GDX",
    # defensie, halfgeleiders
    "DFEN.DE", "ITA", "SEC0.DE", "VVSM.DE", "SOXX",
]
OUT = os.path.join(os.path.dirname(__file__), "data"); os.makedirs(OUT, exist_ok=True)
for t in KANDIDATEN:
    for p in range(3):
        try:
            df = yf.Ticker(t).history(start="2010-01-01", auto_adjust=False)
            if df.empty: raise RuntimeError("leeg")
            df = df[["Close", "Adj Close"]]; df.index = df.index.tz_localize(None).date; df.index.name = "Date"
            df.to_csv(os.path.join(OUT, t.replace(".", "_").replace("=", "_") + ".csv"))
            print(t, len(df), df.index[0], df.index[-1]); break
        except Exception as e:
            print(t, "mislukt", e); time.sleep(5)
    time.sleep(1)
