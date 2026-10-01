# Crypto Proefagent

Papieren handel (fictief geld, €1.000) in een gefilterde selectie crypto's van Crypto.com.
Elke 4 uur draait GitHub automatisch één check:

1. `run.py` haalt live koersen op bij de openbare Crypto.com-API;
2. `bot.py` past de handelsregels toe (trendvolgen en terugveren, met verliesgrenzen);
3. de nieuwe stand komt in `docs/state.json`;
4. het dashboard (`docs/index.html`, via GitHub Pages) laat de stand zien.

Er wordt nergens echt gehandeld en er zijn geen sleutels of wachtwoorden nodig.

**Met de hand een check starten:** tabblad *Actions* → *Crypto Proefagent – check elke 4 uur* → *Run workflow*.
