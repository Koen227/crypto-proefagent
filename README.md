# Crypto Proefagent

Papieren handel (fictief geld, €1.000) op de koersen van Bitvavo. Er wordt nergens echt gehandeld
en er zijn geen sleutels of wachtwoorden nodig: alle gegevens zijn openbaar.

GitHub draait `run.py` elke 15 minuten:

- **elke 15 minuten bewaken:** stopverliezen, winst vastzetten, nieuwsrem;
- **elke 4 uur scannen:** alle euromarkten van Bitvavo bekijken en kansen zoeken met drie strategieën
  (trendvolgen, terugveren, momentum-uitbraak);
- **kosten-batenafweging:** alleen kopen als de verwachte beweging minstens 3x de totale kosten is
  (transactiekosten, bied-laatverschil en wegloop in het orderboek);
- **remmen:** slecht nieuws (aan), extreme hebzucht en veel hefboom (schaduwmodus: alleen meten).

Bestanden:

- `bot.py` – de handelsregels;
- `run.py` – haalt gegevens op en draait één check;
- `data/state.json` – de volledige stand;
- `docs/index.html` + `docs/stand.json` – het dashboard (GitHub Pages).

**Met de hand een check starten:** tabblad *Actions* → *Crypto Proefagent* → *Run workflow*.
