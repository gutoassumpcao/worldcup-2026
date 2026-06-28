#!/usr/bin/env python3
"""
OPTIONAL live-score fetcher (football-data.org free tier).

Enable it by adding a GitHub repository secret FOOTBALL_DATA_TOKEN
(Settings -> Secrets and variables -> Actions -> New repository secret).
Get a free token at https://www.football-data.org/client/register .

It merges any FINISHED match scores into results.json.
- GROUP games are matched by team names against fixtures.json.
- KNOCKOUT games are matched by the REAL teams resolved in data.json's bracket
  (fixtures.json only carries placeholder labels like "RU Group A" for those,
  so they can't be matched by name until the bracket is known). That's why the
  workflow runs build.py BEFORE this script: it resolves the bracket first.

If the token is missing or the competition isn't on your plan, it exits quietly
and the hand-edited results.json is used instead — so nothing breaks either way.

NOTE: if a name doesn't match, extend NAME_MAP below; the run log prints any
UNMATCHED finished games so you can spot new spellings fast.
"""
import json, os, sys, datetime, urllib.request

TOKEN = os.environ.get("FOOTBALL_DATA_TOKEN", "").strip()
if not TOKEN:
    print("No FOOTBALL_DATA_TOKEN set — skipping auto-fetch (edit results.json by hand).")
    sys.exit(0)

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = json.load(open(os.path.join(HERE, "fixtures.json"), encoding="utf-8"))
COMP = "WC"  # football-data.org competition code for the World Cup

# map football-data.org names -> our names (extend as needed)
NAME_MAP = {
    "Korea Republic": "South Korea", "Republic of Korea": "South Korea",
    "USA": "United States", "United States of America": "United States",
    "Türkiye": "Turkey", "Turkiye": "Turkey",
    "Côte d'Ivoire": "Ivory Coast", "Cote d'Ivoire": "Ivory Coast",
    "Czechia": "Czech Republic", "DR Congo": "DR Congo",
    "Congo DR": "DR Congo", "Cabo Verde": "Cape Verde",
    "IR Iran": "Iran", "Bosnia & Herzegovina": "Bosnia and Herzegovina",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina", "Cape Verde Islands": "Cape Verde",
}
def norm(n): return NAME_MAP.get(n, n)

def fetch(path):
    req = urllib.request.Request("https://api.football-data.org/v4" + path,
                                 headers={"X-Auth-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

try:
    payload = fetch(f"/competitions/{COMP}/matches")
except Exception as e:
    print("Fetch failed (plan may not include the World Cup):", e)
    sys.exit(0)

# GROUP games: match by real team names from fixtures.json
GROUP_IDX = {frozenset((m["home"], m["away"])): m
             for m in FIXTURES if m["round"].startswith("Group")}

# KNOCKOUT games: match by the REAL teams resolved in data.json's bracket
KO_IDX = {}
try:
    data = json.load(open(os.path.join(HERE, "data.json"), encoding="utf-8"))
    for mn, b in (data.get("bracket") or {}).items():
        h, a = b.get("home"), b.get("away")
        if h and a:
            KO_IDX[frozenset((h, a))] = {"m": int(mn), "home": h, "away": a}
except Exception:
    pass

results = {}
p = os.path.join(HERE, "results.json")
if os.path.exists(p):
    try: results = json.load(open(p, encoding="utf-8"))
    except Exception: results = {}

added = 0
unmatched = []
for m in payload.get("matches", []):
    if m.get("status") != "FINISHED":
        continue
    h = norm((m.get("homeTeam") or {}).get("name", ""))
    a = norm((m.get("awayTeam") or {}).get("name", ""))
    ft = (m.get("score") or {}).get("fullTime") or {}
    hg, ag = ft.get("home"), ft.get("away")
    if hg is None or ag is None:
        continue
    key = frozenset((h, a))
    stage = (m.get("stage") or "")
    is_group = ("GROUP" in stage) or bool(m.get("group"))
    # route by stage; fall back to the other index if stage info is odd/missing
    fx = (GROUP_IDX.get(key) if is_group else KO_IDX.get(key)) or GROUP_IDX.get(key) or KO_IDX.get(key)
    if fx is None:
        unmatched.append(f"{h} x {a} [{stage or '?'}]"); continue
    results[str(fx["m"])] = f"{hg}-{ag}" if (h == fx["home"] and a == fx["away"]) else f"{ag}-{hg}"
    added += 1

json.dump(results, open(p, "w"), ensure_ascii=False, indent=0)
print("UNMATCHED finished:", unmatched)
print(f"Merged {added} finished results into results.json (total {len(results)}).")
