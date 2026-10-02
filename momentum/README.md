# Momentum Proefagent

Papieren handel (fictief geld, €10.000) in ETF's met een momentumstrategie. Er wordt nergens echt
gehandeld; koersen komen openbaar van Yahoo Finance.

**Regels:** eerste werkdag van de maand → score per ETF = gemiddeld rendement over 1, 3, 6 en 12 maanden;
de 4 hoogste worden gekocht (elk een kwart). Zwakker dan de geldmarkt (XEON) → dat kwart naar de geldmarkt.
Kosten 0,1% per order, minimaal €3.

**Universum (16):** 10 Amerikaanse sectoren (iShares S&P 500 sector), Europa, opkomende markten, Japan,
goud, euro-staatsobligaties; geldmarkt als veilige haven.

**Backtest (okt 2018 – okt 2026), 4 posities:** 14,6% per jaar tegen 13,6% voor de wereld-ETF, grootste daling −14,1%
tegen −18,6%. (Tot 3 okt 2026 draaide de agent met 3 posities.) Uitbreiden met losse opkomende landen, thema's en grondstoffen
(`backtest_uitbreiding.py`) en vooraf 'goed te volgen' ETF's kiezen (`selectie.py`) maakten het niet beter. Alleen regio's (2012–2026): niet beter dan de wereld-ETF. Zie `uitkomst_grid.csv`.

Bestanden: `strategie.py` (regels), `agent.py` (dagelijkse run), `backtest.py`, `state.json` (stand),
`../docs/momentum.html` (dashboard).

**Met de hand starten:** tabblad *Actions* → *Momentum Proefagent* → *Run workflow*.
