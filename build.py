#!/usr/bin/env python3
"""
Regenerates worldcup.ics + data.json from results.json.
- worldcup.ics : the calendar feed your friends subscribe to. Knockout matches
  show PROJECTED real team names as soon as results make them known, and update
  after every game. Group events also carry the head-to-head record in the notes.
- data.json    : feeds the dashboard (index.html) with live results.

results.json format:  { "1": "2-0", "2": "1-1", "73": "0-3", ... }   match number -> "home-away"
Group AND knockout matches both go here. Unplayed matches are omitted.

Standings tie-breaks follow FIFA: points -> goal difference -> goals for ->
then, among teams still level, head-to-head (points, GD, goals) in matches
between them. (Fair play and drawing of lots can't be computed here.)

Best-third-placed slotting uses FIFA's official Annex C table (thirdtable.json,
495 scenarios) once all groups are complete; before that it shows a provisional
valid projection.
"""
import json, datetime, os, re
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
def load(name, default):
    p = os.path.join(HERE, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default

FIXTURES = load("fixtures.json", [])
RAW      = load("results.json", {})
H2H      = load("h2h.json", [])
THIRD_TABLE = load("thirdtable.json", {})

FLAG = {
 "Mexico":"🇲🇽","South Africa":"🇿🇦","South Korea":"🇰🇷","Czech Republic":"🇨🇿","Canada":"🇨🇦",
 "Bosnia and Herzegovina":"🇧🇦","Qatar":"🇶🇦","Switzerland":"🇨🇭","Brazil":"🇧🇷","Morocco":"🇲🇦",
 "Haiti":"🇭🇹","Scotland":"🏴󠁧󠁢󠁳󠁣󠁴󠁿","United States":"🇺🇸","Paraguay":"🇵🇾","Australia":"🇦🇺","Turkey":"🇹🇷",
 "Germany":"🇩🇪","Curaçao":"🇨🇼","Ivory Coast":"🇨🇮","Ecuador":"🇪🇨","Netherlands":"🇳🇱","Japan":"🇯🇵",
 "Sweden":"🇸🇪","Tunisia":"🇹🇳","Belgium":"🇧🇪","Egypt":"🇪🇬","Iran":"🇮🇷","New Zealand":"🇳🇿",
 "Spain":"🇪🇸","Cape Verde":"🇨🇻","Saudi Arabia":"🇸🇦","Uruguay":"🇺🇾","France":"🇫🇷","Senegal":"🇸🇳",
 "Iraq":"🇮🇶","Norway":"🇳🇴","Argentina":"🇦🇷","Algeria":"🇩🇿","Austria":"🇦🇹","Jordan":"🇯🇴",
 "Portugal":"🇵🇹","DR Congo":"🇨🇩","Uzbekistan":"🇺🇿","Colombia":"🇨🇴","England":"🏴󠁧󠁢󠁥󠁮󠁗󠁿","Croatia":"🇭🇷",
 "Ghana":"🇬🇭","Panama":"🇵🇦",
}
FLAG["England"]="🏴󠁧󠁢󠁥󠁮󠁧󠁿"

# ---- head-to-head lookup ----
def hk(a, b): return tuple(sorted([a, b]))
HM = {hk(r["a"], r["b"]): r for r in H2H}
def h2h_desc(home, away):
    r = HM.get(hk(home, away))
    if not r: return ""
    if r.get("p", 0) == 0:
        return f"Head-to-head: {home} and {away} have never met — a first-ever meeting."
    if r.get("aw") is None:
        s = f"Head-to-head: {r['p']} played."
        if r.get("res"): s += f" Last: {r['res']}" + (f" ({str(r['last'])[:4]})" if r.get("last") else "") + "."
        return s
    hw, aw = (r["aw"], r["bw"]) if r["a"] == home else (r["bw"], r["aw"])
    s = f"Head-to-head: {r['p']} played — {home} {hw}, draws {r['d']}, {away} {aw}."
    if r.get("res"): s += f" Last: {r['res']}" + (f" ({str(r['last'])[:4]})" if r.get("last") else "") + "."
    return s

# ---- parse results ----
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
        Lg = m["round"][6:]
        GROUPS.setdefault(Lg, [])
        for t in (m["home"], m["away"]):
            if t not in GROUPS[Lg]: GROUPS[Lg].append(t)
GL = sorted(GROUPS)

def mini_h2h(teams, Lg):
    s = {t: {"p":0,"gd":0,"gf":0} for t in teams}
    for m in FIXTURES:
        if m["round"] != "Group "+Lg: continue
        r = RES.get(m["m"]);
        if not r: continue
        if m["home"] not in s or m["away"] not in s: continue
        h, a = s[m["home"]], s[m["away"]]
        h["gf"]+=r["h"]; a["gf"]+=r["a"]; h["gd"]+=r["h"]-r["a"]; a["gd"]+=r["a"]-r["h"]
        if r["h"]>r["a"]: h["p"]+=3
        elif r["h"]<r["a"]: a["p"]+=3
        else: h["p"]+=1; a["p"]+=1
    return s

def standings(Lg):
    st = {t: dict(t=t,P=0,W=0,D=0,L=0,GF=0,GA=0,GD=0,Pts=0) for t in GROUPS[Lg]}
    for m in FIXTURES:
        if m["round"] != "Group "+Lg: continue
        r = RES.get(m["m"]);
        if not r: continue
        h, a = st[m["home"]], st[m["away"]]
        h["P"]+=1; a["P"]+=1; h["GF"]+=r["h"]; h["GA"]+=r["a"]; a["GF"]+=r["a"]; a["GA"]+=r["h"]
        if r["h"]>r["a"]: h["W"]+=1; a["L"]+=1; h["Pts"]+=3
        elif r["h"]<r["a"]: a["W"]+=1; h["L"]+=1; a["Pts"]+=3
        else: h["D"]+=1; a["D"]+=1; h["Pts"]+=1; a["Pts"]+=1
    for s in st.values(): s["GD"] = s["GF"]-s["GA"]
    arr = sorted(st.values(), key=lambda s:(-s["Pts"],-s["GD"],-s["GF"]))
    out=[]; i=0
    while i < len(arr):
        j=i+1
        while j<len(arr) and (arr[j]["Pts"],arr[j]["GD"],arr[j]["GF"])==(arr[i]["Pts"],arr[i]["GD"],arr[i]["GF"]): j+=1
        cl=arr[i:j]
        if len(cl)>1:
            mh=mini_h2h([s["t"] for s in cl], Lg)
            cl.sort(key=lambda s:(-mh[s["t"]]["p"],-mh[s["t"]]["gd"],-mh[s["t"]]["gf"],s["t"]))
        out+=cl; i=j
    return out

def group_complete(Lg):
    return all(RES.get(m["m"]) for m in FIXTURES if m["round"]=="Group "+Lg)

def thirds_ranking():
    arr=[(Lg, standings(Lg)[2]) for Lg in GL]
    arr=[(Lg,s) for Lg,s in arr if s["P"]>0]
    arr.sort(key=lambda x:(-x[1]["Pts"],-x[1]["GD"],-x[1]["GF"],x[0]))
    return arr

THIRD_COL_SLOTS=[79,85,81,74,82,77,87,80]   # columns 1A,1B,1D,1E,1G,1I,1K,1L
THIRD_SLOT_ALLOW={74:"ABCDF",77:"CDFGH",79:"CEFHI",80:"EHIJK",81:"BEFIJ",82:"AEHIJ",85:"EFGIJ",87:"DEIJL"}
def assign_thirds():
    ranked=thirds_ranking()
    qualified=[Lg for Lg,_ in ranked[:8]]
    all_done=all(group_complete(Lg) for Lg in GL)
    if all_done and len(qualified)==8:
        key="".join(sorted(qualified))
        a=THIRD_TABLE.get(key)
        if a and len(a)==8:
            return {THIRD_COL_SLOTS[c]: a[c] for c in range(8)}   # OFFICIAL
    slots=list(THIRD_SLOT_ALLOW); used=set(); res={}
    def bt(i):
        if i==len(slots): return True
        for Lg in qualified:
            if Lg in used or Lg not in THIRD_SLOT_ALLOW[slots[i]]: continue
            used.add(Lg); res[slots[i]]=Lg
            if bt(i+1): return True
            used.discard(Lg); res.pop(slots[i],None)
        return False
    return res if (len(qualified)==8 and bt(0)) else {}

THIRDS = assign_thirds()

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
    mo=re.match(r"^W Group ([A-L])$", label)
    if mo: s=standings(mo[1]); return s[0]["t"] if group_complete(mo[1]) else None
    mo=re.match(r"^RU Group ([A-L])$", label)
    if mo: s=standings(mo[1]); return s[1]["t"] if group_complete(mo[1]) else None
    if label.startswith("3rd "):
        Lg=THIRDS.get(matchnum)
        return standings(Lg)[2]["t"] if (Lg and group_complete(Lg)) else None
    mo=re.match(r"^W Match (\d+)$", label)
    if mo: return winner_of(int(mo[1]))
    mo=re.match(r"^L Match (\d+)$", label)
    if mo: return loser_of(int(mo[1]))
    return None
def teams_of(mn):
    m=BYNUM[mn]
    if m["round"].startswith("Group"): return m["home"], m["away"]
    return resolve(m["home"], mn), resolve(m["away"], mn)

# ---- ICS ----
def dt_utc(m):
    y,mo,d=map(int,m["date"].split("-")); hh,mm=map(int,m["time"].split(":"))
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

stamp=fmt(datetime.datetime.now(datetime.timezone.utc))
L=["BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//Guto Assumpção//World Cup 2026 Live//EN","CALSCALE:GREGORIAN",
   "METHOD:PUBLISH","X-WR-CALNAME:FIFA World Cup 2026 (Live)",
   fold("X-WR-CALDESC:Auto-updating. Knockout teams fill in as results come. Created by Guto Assumpção (@GutoAssumpcao) · instagram.com/GutoAssumpcao"),
   "REFRESH-INTERVAL;VALUE=DURATION:PT6H","X-PUBLISHED-TTL:PT6H"]
for m in FIXTURES:
    grp=m["round"].startswith("Group")
    home,away=teams_of(m["m"]); home=home or m["home"]; away=away or m["away"]
    r=RES.get(m["m"])
    if grp:
        sc=f" {r['h']}–{r['a']} " if r else " vs "
        summary=f"{FLAG.get(home,'')} {home}{sc}{away} {FLAG.get(away,'')} · {m['round']}"
    else:
        rn=m["round"].replace("Round of 32","R32").replace("Round of 16","R16").replace("Quarter-final","QF").replace("Semi-final","SF")
        kn=lambda x:x.replace("W Group ","Winner ").replace("RU Group ","Runner-up ").replace("W Match ","Winner M").replace("L Match ","Loser M")
        hn=home if not home.startswith(("W ","RU ","3rd ","L ")) else kn(home)
        an=away if not away.startswith(("W ","RU ","3rd ","L ")) else kn(away)
        sc=f" {r['h']}–{r['a']} " if r else " vs "
        summary=f"{rn}: {hn}{sc}{an}"
    start=dt_utc(m); end=start+datetime.timedelta(hours=2)
    desc=f"Match {m['m']} · {m['round']} · kick-off {m['time']} local ({m['city']}). Venue: {m['stadium']}."
    if grp:
        h=h2h_desc(m["home"], m["away"])
        if h: desc += "  " + h
    elif not r:
        desc += "  Teams confirm as earlier rounds finish — the feed updates automatically."
    L+=["BEGIN:VEVENT", f"UID:wc2026-m{m['m']}@worldcup", f"DTSTAMP:{stamp}",
        f"DTSTART:{fmt(start)}", f"DTEND:{fmt(end)}",
        fold(f"SUMMARY:{esc(summary)}"), fold(f"LOCATION:{esc(m['stadium']+', '+m['city'])}"),
        fold(f"DESCRIPTION:{esc(desc)}"),
        f"CATEGORIES:{esc(m['round'])}", "STATUS:CONFIRMED", "END:VEVENT"]
L.append("END:VCALENDAR")
open(os.path.join(HERE,"worldcup.ics"),"w",encoding="utf-8").write("\r\n".join(L)+"\r\n")

# ---- data.json ----
bracket={}
for m in FIXTURES:
    if not m["round"].startswith("Group"):
        h,a=teams_of(m["m"]); bracket[m["m"]]={"home":h,"away":a,"winner":winner_of(m["m"])}
data={"updated":datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
      "results":RES, "standings":{L0:standings(L0) for L0 in GL}, "bracket":bracket}
open(os.path.join(HERE,"data.json"),"w",encoding="utf-8").write(json.dumps(data,ensure_ascii=False,indent=1))
print(f"Built worldcup.ics + data.json · {len(RES)} results · thirds: {len(THIRDS)}/8 slots")
