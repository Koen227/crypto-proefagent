"""Maakt de claude.ai-artifactversie van het dashboard: docs/momentum.html met de laatste stand (docs/momentum.json) erin."""
import os
import sys
OUT = sys.argv[1] if len(sys.argv) > 1 else "momentum-artifact.html"
R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs") + "/"
s = open(R + "momentum.html").read()
snap = open(R + "momentum.json").read().replace("</", "<\\/")

old = 'fetch("momentum.json?"+Date.now()).then(r=>r.json()).then(s=>{'
assert old in s
s = s.replace(old, '''const RAW="https://raw.githubusercontent.com/Koen227/crypto-proefagent/main/docs/momentum.json";
const LIVE="https://koen227.github.io/crypto-proefagent/momentum.html";
let bron="live";
fetch(RAW+"?"+Date.now()).then(r=>{if(!r.ok)throw 0;return r.json()}).catch(()=>{bron="snap";return JSON.parse(document.getElementById("snap").textContent)}).then(s=>{''')

oldm = '<a href="./">naar de Crypto Proefagent</a>`;'
assert oldm in s
s = s.replace(oldm, '`+(bron=="live"?"live uit GitHub":`momentopname, <a href="${LIVE}" target="_blank" rel="noopener">actuele stand op het dashboard</a>`);')

assert "<script>\nconst eur" in s
s = s.replace("<script>\nconst eur", '<script id="snap" type="application/json">' + snap + "</script>\n<script>\nconst eur")
s = s.replace('meta.textContent="Nog geen gegevens. De agent draait elke werkdag rond 19:45 uur."', 'meta.textContent="Gegevens konden niet worden geladen."')
open(OUT, "w").write(s)
print("ok", len(s))
