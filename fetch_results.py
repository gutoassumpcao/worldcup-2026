#!/usr/bin/env python3
"""
OPTIONAL live-score fetcher (football-data.org free tier).

Enable it by adding a GitHub repository secret FOOTBALL_DATA_TOKEN
(Settings -> Secrets and variables -> Actions -> New repository secret).
Get a free token at https://www.football-data.org/client/register .

It merges any FINISHED match scores into results.json, matching by team names
and date against fixtures.json. If the token is missing or the competition
isn't available on your plan, it exits quietly and the hand-edited results.json
is used instead — so nothing breaks either way.

NOTE: free-tier coverage of the men's World Cup and exact team-name spellings
can vary. After the first matches kick off, open an Action run log and confirm
results.json is filling in; if names don't match, extend NAME_MAP below.
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

# index our fixtures by (home, away)
idx = {frozenset((m["home"], m["away"])): m for m in FIXTURES}
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
    fx = idx.get(frozenset((h, a)))
    if fx is None:
        unmatched.append(f"{h} x {a}"); continue
    results[str(fx["m"])] = f"{hg}-{ag}" if (h==fx["home"] and a==fx["away"]) else f"{ag}-{hg}"
    added += 1

json.dump(results, open(p, "w"), ensure_ascii=False, indent=0)
print("UNMATCHED finished:", unmatched)
print(f"Merged {added} finished results into results.json (total {len(results)}).")
