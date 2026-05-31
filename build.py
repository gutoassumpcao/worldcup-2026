#!/usr/bin/env python3
"""
Regenerates worldcup.ics + data.json from results.json.
- worldcup.ics : the calendar feed your friends subscribe to. Knockout matches
  show PROJECTED real team names as soon as results make them known, and update
  after every game. This is what makes the feed live instead of static.
- data.json    : feeds the dashboard (index.html) with live results.

Run locally:  python build.py
In CI: the GitHub Action runs this on a schedule and commits any changes.

results.json format (you OR the fetch step fill this in):
  { "1": "2-0", "2": "1-1", "73": "0-3", ... }    # match number -> "home-away"
Group AND knockout matches both go here. Unplayed matches are simply omitted.
"""
import json, datetime, os
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
def load(name, default):
    p = os.path.join(HERE, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default

FIXTURES = load("fixtures.json", [])
RAW = load("results.json", {})

FLAG = {
 "Mexico":"🇲🇽","South Africa":"🇿🇦","South Korea":"🇰🇷","Czech Republic":"🇨🇿","Canada":"🇨🇦",
 "Bosnia and Herzegovina":"🇧🇦","Qatar":"🇶🇦","Switzerland":"🇨🇭","Brazil":"🇧🇷","Morocco":"🇲🇦",
 "Haiti":"🇭🇹","Scotland":"🏴󠁧󠁢󠁳󠁣󠁴󠁿","United States":"🇺🇸","Paraguay":"🇵🇾","Australia":"🇦🇺","Turkey":"🇹🇷",
 "Germany":"🇩🇪","Curaçao":"🇨🇼","Ivory Coast":"🇨🇮","Ecuador":"🇪🇨","Netherlands":"🇳🇱","Japan":"🇯🇵",
 "Sweden":"🇸🇪","Tunisia":"🇹🇳","Belgium":"🇧🇪","Egypt":"🇪🇬","Iran":"🇮🇷","New Zealand":"🇳🇿",
 "Spain":"🇪🇸","Cape Verde":"🇨🇻","Saudi Arabia":"🇸🇦","Uruguay":"🇺🇾","France":"🇫🇷","Senegal":"🇸🇳",
 "Iraq":"🇮🇶","Norway":"🇳🇴","Argentina":"🇦🇷","Algeria":"🇩🇿","Austria":"🇦🇹","Jordan":"🇯🇴",
 "Portugal":"🇵🇹","DR Congo":"🇨🇩","Uzbekistan":"🇺🇿","Colombia":"🇨🇴","England":"🏴󠁧󠁢󠁥󠁮󠁧󠁿","Croatia":"🇭🇷",
 "Ghana":"🇬🇭","Panama":"🇵🇦",
}

# ---- parse results into {num:{h,a}} ----
RES = {}
for k, v in RAW.items():
    try:
        if isinstance(v, str) and "-" in v:
            h, a = v.split("-"); RES[int(k)] = {"h": int(h), "a": int(a)}
        elif isinstance(v, dict) and "h" in v and "a" in v:
            RES[int(k)] = {"h": int(v["h"]), "a": int(v["a"])}
    except Exception:
        pass

BYNUM = {m["m"]: m for m in FIXTURES}
GROUPS = {}
for m in FIXTURES:
    if m["round"].startswith("Group"):
        L = m["round"][6:]
        GROUPS.setdefault(L, [])
        for t in (m["home"], m["away"]):
            if t not in GROUPS[L]:
                GROUPS[L].append(t)
GL = sorted(GROUPS)

def standings(L):
    st = {t: dict(t=t,P=0,W=0,D=0,L=0,GF=0,GA=0,GD=0,Pts=0) for t in GROUPS[L]}
    for m in FIXTURES:
        if m["round"] != "Group "+L: continue
        r = RES.get(m["m"]);
        if not r: continue
        h, a = st[m["home"]], st[m["away"]]
        h["P"]+=1; a["P"]+=1; h["GF"]+=r["h"]; h["GA"]+=r["a"]; a["GF"]+=r["a"]; a["GA"]+=r["h"]
        if r["h"]>r["a"]: h["W"]+=1; a["L"]+=1; h["Pts"]+=3
        elif r["h"]<r["a"]: a["W"]+=1; h["L"]+=1; a["Pts"]+=3
        else: h["D"]+=1; a["D"]+=1; h["Pts"]+=1; a["Pts"]+=1
    for s in st.values(): s["GD"] = s["GF"]-s["GA"]
    return sorted(st.values(), key=lambda s:(-s["Pts"],-s["GD"],-s["GF"],s["t"]))

def group_complete(L):
    return all(RES.get(m["m"]) for m in FIXTURES if m["round"]=="Group "+L)

THIRD_SLOTS = {74:"ABCDF",77:"CDFGH",79:"CEFHI",80:"EHIJK",81:"BEFIJ",82:"AEHIJ",85:"EFGIJ",87:"DEIJL"}
def assign_thirds():
    ranked = [(L, standings(L)[2]) for L in GL]
    ranked = [(L,s) for L,s in ranked if s["P"]>0]
    ranked.sort(key=lambda x:(-x[1]["Pts"],-x[1]["GD"],-x[1]["GF"],x[0]))
    qualified = [L for L,_ in ranked[:8]]
    slots = list(THIRD_SLOTS); used=set(); result={}
    def bt(i):
        if i==len(slots): return True
        slot=slots[i]
        for L in qualified:
            if L in used or L not in THIRD_SLOTS[slot]: continue
            used.add(L); result[slot]=L
            if bt(i+1): return True
            used.discard(L); result.pop(slot,None)
        return False
    ok = len(qualified)==8 and bt(0)
    return result if ok else {}

THIRDS = assign_thirds()

import re
def winner_of(mn):
    r = RES.get(mn)
    if not r: return None
    home, away = teams_of(mn)
    if not home or not away: return None
    if r["h"]>r["a"]: return home
    if r["a"]>r["h"]: return away
    return None
def loser_of(mn):
    w = winner_of(mn)
    if not w: return None
    home, away = teams_of(mn)
    return away if w==home else (home if w==away else None)
def resolve(label, matchnum):
    mo = re.match(r"^W Group ([A-L])$", label)
    if mo: s=standings(mo[1]); return s[0]["t"] if group_complete(mo[1]) else None
    mo = re.match(r"^RU Group ([A-L])$", label)
    if mo: s=standings(mo[1]); return s[1]["t"] if group_complete(mo[1]) else None
    if label.startswith("3rd "):
        L = THIRDS.get(matchnum)
        return standings(L)[2]["t"] if (L and group_complete(L)) else None
    mo = re.match(r"^W Match (\d+)$", label)
    if mo: return winner_of(int(mo[1]))
    mo = re.match(r"^L Match (\d+)$", label)
    if mo: return loser_of(int(mo[1]))
    return None
def teams_of(mn):
    m = BYNUM[mn]
    if m["round"].startswith("Group"): return m["home"], m["away"]
    return resolve(m["home"], mn), resolve(m["away"], mn)

# ---- ICS ----
def dt_utc(m):
    y,mo,d = map(int,m["date"].split("-")); hh,mm = map(int,m["time"].split(":"))
    return datetime.datetime(y,mo,d,hh,mm,tzinfo=ZoneInfo(m["tz"])).astimezone(datetime.timezone.utc)
def fmt(dt): return dt.strftime("%Y%m%dT%H%M%SZ")
def esc(s): return s.replace("\\","\\\\").replace(";","\\;").replace(",","\\,").replace("\n","\\n")
def fold(line):
    if len(line.encode("utf-8"))<=73: return line
    out, cur = [], b""
    for ch in line:
        e=ch.encode("utf-8")
        if len(cur)+len(e)>73: out.append(cur.decode()); cur=b" "+e
        else: cur+=e
    out.append(cur.decode()); return "\r\n".join(out)

stamp = fmt(datetime.datetime.now(datetime.timezone.utc))
L = ["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//WorldCup2026 Live//EN","CALSCALE:GREGORIAN",
     "METHOD:PUBLISH","X-WR-CALNAME:FIFA World Cup 2026 (Live)",
     "X-WR-CALDESC:Auto-updating. Knockout teams fill in as results come.",
     "REFRESH-INTERVAL;VALUE=DURATION:PT6H","X-PUBLISHED-TTL:PT6H"]
for m in FIXTURES:
    grp = m["round"].startswith("Group")
    home, away = teams_of(m["m"])
    home = home or m["home"]; away = away or m["away"]
    r = RES.get(m["m"])
    if grp:
        sc = f" {r['h']}–{r['a']} " if r else " vs "
        summary = f"{FLAG.get(home,'')} {home}{sc}{away} {FLAG.get(away,'')} · {m['round']}"
    else:
        rn = m["round"].replace("Round of 32","R32").replace("Round of 16","R16").replace("Quarter-final","QF").replace("Semi-final","SF")
        kn = lambda x: x.replace("W Group ","Winner ").replace("RU Group ","Runner-up ").replace("W Match ","Winner M").replace("L Match ","Loser M")
        hn = home if not home.startswith(("W ","RU ","3rd ","L ")) else kn(home)
        an = away if not away.startswith(("W ","RU ","3rd ","L ")) else kn(away)
        sc = f" {r['h']}–{r['a']} " if r else " vs "
        summary = f"{rn}: {hn}{sc}{an}"
    start = dt_utc(m); end = start + datetime.timedelta(hours=2)
    desc = f"Match {m['m']} · {m['round']} · kick-off {m['time']} local ({m['city']})."
    L += ["BEGIN:VEVENT", f"UID:wc2026-m{m['m']}@worldcup", f"DTSTAMP:{stamp}",
          f"DTSTART:{fmt(start)}", f"DTEND:{fmt(end)}",
          fold(f"SUMMARY:{esc(summary)}"), fold(f"LOCATION:{esc(m['stadium']+', '+m['city'])}"),
          fold(f"DESCRIPTION:{esc(desc)}"),
          f"CATEGORIES:{esc(m['round'])}", "STATUS:CONFIRMED", "END:VEVENT"]
L.append("END:VCALENDAR")
open(os.path.join(HERE,"worldcup.ics"),"w",encoding="utf-8").write("\r\n".join(L)+"\r\n")

# ---- data.json for the dashboard ----
bracket = {}
for m in FIXTURES:
    if not m["round"].startswith("Group"):
        h,a = teams_of(m["m"])
        bracket[m["m"]] = {"home":h, "away":a, "winner":winner_of(m["m"])}
data = {"updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "results": RES,
        "standings": {L0: standings(L0) for L0 in GL},
        "bracket": bracket}
open(os.path.join(HERE,"data.json"),"w",encoding="utf-8").write(json.dumps(data,ensure_ascii=False,indent=1))
print(f"Built worldcup.ics + data.json · {len(RES)} results · thirds slots filled: {len(THIRDS)}/8")
