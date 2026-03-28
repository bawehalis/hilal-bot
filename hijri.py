import logging
from datetime import datetime, timedelta, timezone, date

from skyfield.api import load
from skyfield.almanac import find_discrete, moon_phases, sunrise_sunset

from criteria import get_criterion, DEFAULT_CRITERION
from locations import get_all_locations

logger = logging.getLogger(**name**)

_ts    = None
_eph   = None
_earth = None
_moon  = None
_sun   = None

EPH_FILE = “de440.bsp”

def get_sf():
global _ts, _eph, _earth, _moon, _sun
if _ts is None:
_ts = load.timescale()
try:
_eph = load(EPH_FILE)
logger.info(”%s yuklendi.”, EPH_FILE)
except Exception:
try:
_eph = load(“de421.bsp”)
logger.info(“de421.bsp yuklendi.”)
except Exception:
from skyfield.api import Loader
_eph = Loader(”.”)(“de421.bsp”)
_earth = _eph[“earth”]
_moon  = _eph[“moon”]
_sun   = _eph[“sun”]
return _ts, _eph, _earth, _moon, _sun

_nm_cache = None

def get_new_moons():
global _nm_cache
if _nm_cache:
return *nm_cache
ts, eph, ** = get_sf()
times, phases = find_discrete(ts.utc(1990, 1, 1), ts.utc(2040, 12, 31), moon_phases(eph))
_nm_cache = [
t.utc_datetime().replace(tzinfo=timezone.utc)
for t, p in zip(times, phases) if p == 0
]
return _nm_cache

def get_sunset_utc(loc, y, mo, d):
ts, eph, *_ = get_sf()
try:
t0 = ts.utc(y, mo, d, 12)
t1 = ts.utc(y, mo, d + 1, 6)
times, events = find_discrete(t0, t1, sunrise_sunset(eph, loc))
for t, e in zip(times, events):
if e == 0:
return t.utc_datetime().hour + t.utc_datetime().minute / 60.0
except Exception:
pass
return 18.0

def odeh_q(alt, elong):
return alt - (7.1651 - 6.3226*(elong*0.01) + 7.0482*(elong*0.01)**2 - 0.3014*(elong*0.01)**3)

def check_hilal(d, nm, criterion_name=DEFAULT_CRITERION):
ts, eph, earth, moon, sun = get_sf()
criterion = get_criterion(criterion_name)
locs = get_all_locations()

```
best_q   = -99.0
best_loc = ""
gorunur  = False
detaylar = {}

for loc_name, loc in locs.items():
    sh = get_sunset_utc(loc, d.year, d.month, d.day)
    best_q_loc = -99.0
    best_alt   = -99.0
    best_elong = 0.0

    for off in range(15, 70, 5):
        hf = sh + off / 60.0
        h  = int(hf)
        mi = int((hf % 1) * 60)
        if h >= 24:
            break

        t     = ts.utc(d.year, d.month, d.day, h, mi)
        obs   = (earth + loc).at(t)
        m_app = obs.observe(moon).apparent()
        s_app = obs.observe(sun).apparent()
        alt_deg = m_app.altaz()[0].degrees
        elong   = m_app.separation_from(s_app).degrees

        if alt_deg <= 0:
            continue

        sunset_dt = datetime(d.year, d.month, d.day,
                             int(sh), int((sh % 1) * 60),
                             tzinfo=timezone.utc)
        age_hours = (sunset_dt - nm).total_seconds() / 3600.0
        if age_hours < 13.5:
            continue

        q = criterion.score(alt_deg, elong, age_hours)
        if q > best_q_loc:
            best_q_loc = q
            best_alt   = alt_deg
            best_elong = elong

    detaylar[loc_name] = {"alt": best_alt, "elong": best_elong, "q": best_q_loc}

    if best_q_loc > best_q:
        best_q   = best_q_loc
        best_loc = loc_name

    if criterion.is_visible(best_alt, best_elong):
        gorunur = True

return gorunur, best_q, best_loc, detaylar
```

def prev_conjunction(d):
nms = get_new_moons()
best = None
for nm in nms:
if nm.date() <= d:
best = nm
else:
break
return best

_cal_cache = None

ANCHOR_DATE     = date(2025, 3, 1)
ANCHOR_AY_INDEX = 8

def build_cal():
global _cal_cache
if _cal_cache:
return _cal_cache
logger.info(“Takvim insa ediliyor…”)
nms = get_new_moons()

```
nm0 = nms[0]
d1  = nm0.date() + timedelta(days=1)
g, _, _, _ = check_hilal(d1, nm0)
months = [d1 if g else d1 + timedelta(days=1)]

for _ in range(620):
    prev  = months[-1]
    gun29 = prev + timedelta(days=28)
    nm    = prev_conjunction(gun29)
    if nm is None:
        break
    g, _, _, _ = check_hilal(gun29, nm)
    months.append(gun29 + timedelta(days=1 if g else 2))
    if months[-1].year > 2040:
        break

_cal_cache = months
logger.info("Takvim hazir: %d ay", len(_cal_cache))
return _cal_cache
```

def _muharrem_1446():
cal = build_cal()
idx = min(range(len(cal)), key=lambda i: abs((cal[i] - ANCHOR_DATE).days))
return idx - ANCHOR_AY_INDEX

AYLAR_TR = [
“Muharrem”, “Safer”, “Rebi\u00fclevvel”, “Rebi\u00fclahir”,
“Cemaziyelevvel”, “Cemaziyelahir”, “Recep”,
“\u015eaban”, “Ramazan”, “\u015eevval”, “Zilkade”, “Zilhicce”
]

def ay_adi(hay, tr=True):
if 1 <= hay <= 12:
return AYLAR_TR[hay - 1]
return “?”

def miladi_to_hicri(d, criterion_name=DEFAULT_CRITERION):
cal   = build_cal()
m1446 = _muharrem_1446()
cur   = None
for i, m in enumerate(cal):
if m <= d:
cur = (m, i)
if not cur:
return 0, “?”, -1, 0
start, idx = cur
gun   = (d - start).days + 1
delta = idx - m1446
hay   = delta % 12 + 1
hyil  = 1446 + delta // 12
return gun, AYLAR_TR[delta % 12], hay, hyil

def get_month_start(hyil, hay):
cal   = build_cal()
m1446 = _muharrem_1446()
delta = (hyil - 1446) * 12 + (hay - 1)
idx   = m1446 + delta
if 0 <= idx < len(cal):
return cal[idx]
return None

def ramazan_basi(yil, criterion_name=DEFAULT_CRITERION):
return get_month_start(yil, 9)

def sevval_basi(yil, criterion_name=DEFAULT_CRITERION):
return get_month_start(yil, 10)