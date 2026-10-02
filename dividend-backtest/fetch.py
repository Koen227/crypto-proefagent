"""Haalt 10+ jaar dagkoersen (niet gecorrigeerd voor dividend) en dividenden op
voor de kandidaten van de dividend-test. Resultaat: dividend-backtest/data/*.csv"""
import os, time
import yfinance as yf

TICKERS = [
    # Nederland / Amsterdam
    "KPN.AS", "SHELL.AS", "UNA.AS", "INGA.AS", "ABN.AS", "NN.AS", "ASRNL.AS",
    "AD.AS", "WKL.AS", "HEIA.AS", "RAND.AS", "ASML.AS",
    # Verenigde Staten
    "KO", "PEP", "PG", "JNJ", "MCD", "CL", "KMB", "WMT", "DUK", "SO", "ED", "VZ",
    # vergelijking: wereld-ETF
    "IWDA.AS",
]
OUT = os.path.join(os.path.dirname(__file__), "data")
os.makedirs(OUT, exist_ok=True)

for t in TICKERS:
    for poging in range(3):
        try:
            df = yf.Ticker(t).history(start="2015-01-01", auto_adjust=False, actions=True)
            if df.empty:
                raise RuntimeError("leeg")
            df = df[["Open", "Close", "Adj Close", "Dividends", "Stock Splits"]]
            df.index = df.index.tz_localize(None).date
            df.index.name = "Date"
            df.to_csv(os.path.join(OUT, t.replace(".", "_") + ".csv"))
            print(t, len(df), "dagen,", int((df["Dividends"] > 0).sum()), "dividenden")
            break
        except Exception as e:
            print(t, "poging", poging + 1, "mislukt:", e)
            time.sleep(10)
    time.sleep(2)
