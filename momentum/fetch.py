"""Haalt dagkoersen op van kandidaat-ETF's (UCITS, kopen kan vanuit NL) voor de momentum-backtest."""
import os, time
import yfinance as yf
KANDIDATEN = [
    # regio's (EUR, Xetra/Amsterdam)
    "IWDA.AS", "SXR8.DE", "EQQQ.DE", "EXSA.DE", "IS3N.DE", "EUNM.DE", "SXR7.DE", "EXX7.DE",
    "IJPA.AS", "SJPA.L", "XMJP.DE", "IUSN.DE", "ZPRV.DE", "EXSE.DE",
    # Amerikaanse sectoren (iShares S&P 500 sector, USD op Londen)
    "IUIT.L", "IUHC.L", "IUFS.L", "IUES.L", "IUCD.L", "IUCS.L", "IUIS.L", "IUUS.L", "IUMS.L", "IUCM.L",
    # goud, obligaties, geldmarkt
    "4GLD.DE", "SGLD.L", "XGLE.DE", "EUNH.DE", "IBGS.AS", "XEON.DE", "CSH2.PA",
    # wisselkoers
    "EURUSD=X",
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
