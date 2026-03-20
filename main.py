import os
import logging
import math
import asyncio
from datetime import datetime, timedelta, timezone, date

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from skyfield.api import load, wgs84
from skyfield.almanac import find_discrete, moon_phases, sunrise_sunset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise EnvironmentError("TOKEN env var missing")

_ts = _eph = _earth = _moon = _sun = None

def sf():
    global _ts, _eph, _earth, _moon, _sun
    if _ts is None:
        _ts = load.timescale()
        try:
            _eph = load("de421.bsp")
        except Exception:
            from skyfield.api import Loader
            _eph = Loader(".")("de421.bsp")
        _earth = _eph["earth"]
        _moon  = _eph["moon"]
        _sun   = _eph["sun"]
    return _ts, _eph, _earth, _moon, _sun

_nm_cache  = None
_cal_cache = None

def new_moons():
    global _nm_cache
    if _nm_cache: return _nm_cache
    ts, eph, *_ = sf()
    times, phases = find_discrete(ts.utc(1990,1,1), ts.utc(2040,12,31), moon_phases(eph))
    _nm_cache = [t.utc_datetime().replace(tzinfo=timezone.utc) for t,p in zip(times,phases) if p==0]
    return _nm_cache

LOCS = {
    "Mekke":    wgs84.latlon(21.4225, 39.8262),
    "Medine":   wgs84.latlon(24.4672, 39.6151),
    "Ankara":   wgs84.latlon(39.9334, 32.8597),
    "Istanbul": wgs84.latlon(41.0082, 28.9784),
    "Tahran":   wgs84.latlon(35.6892, 51.3890),
    "Kahire":   wgs84.latlon(30.0444, 31.2357),
    "Bagdat":   wgs84.latlon(33.3406, 44.4009),
    "Karaci":   wgs84.latlon(24.8607, 67.0011),
}

def sunset_utc(loc, y, mo, d):
    ts, eph, *_ = sf()
    try:
        times, events = find_discrete(
            ts.utc(y,mo,d,12), ts.utc(y,mo,d,23,59), sunrise_sunset(eph,loc)
        )
        for t,e in zip(times,events):
            if e==0: return t.utc_datetime().hour + t.utc_datetime().minute/60.0
    except: pass
    return 18.0

def odeh_q(alt, elong):
    return alt - (7.1651 - 6.3226*(elong*0.01) + 7.0482*(elong*0.01)**2 - 0.3014*(elong*0.01)**3)

def hilal(d, nm):
    ts, eph, earth, moon, sun = sf()
    best_q  = -99.0
    gorunur = False
    for loc in LOCS.values():
        sh = sunset_utc(loc, d.year, d.month, d.day)
        for off in range(15, 70, 5):
            hf = sh + off/60.0
            h, mi = int(hf), int((hf%1)*60)
            if h >= 24: break
            t     = ts.utc(d.year, d.month, d.day, h, mi)
            obs   = (earth + loc).at(t)
            m_app = obs.observe(moon).apparent()
            s_app = obs.observe(sun).apparent()
            alt_deg = m_app.altaz()[0].degrees
            elong   = m_app.separation_from(s_app).degrees
            if alt_deg <= 0: continue
            sunset_dt = datetime(d.year, d.month, d.day,
                                 int(sh), int((sh%1)*60), tzinfo=timezone.utc)
            if (sunset_dt - nm).total_seconds()/3600 < 13.5: continue
            q = odeh_q(alt_deg, elong)
            if q > best_q: best_q = q
            if q >= 0.0: gorunur = True
    return gorunur, best_q

def nm_bul(d):
    nms = new_moons()
    for nm in nms:
        if nm.date() >= d - timedelta(days=3):
            return nm
    return nms[-1]

def build_cal():
    global _cal_cache
    if _cal_cache: return _cal_cache

    logger.info("Takvim insa ediliyor...")

    nms = new_moons()
    nm0 = nms[0]
    d1  = nm0.date() + timedelta(days=1)
    g, _ = hilal(d1, nm0)
    months = [d1 if g else d1 + timedelta(days=1)]

    for _ in range(620):
        prev  = months[-1]
        gun29 = prev + timedelta(days=28)
        nm    = nm_bul(gun29)
        if nm is None: break
        g, _ = hilal(gun29, nm)
        months.append(gun29 + timedelta(days=1 if g else 2))
        if months[-1].year > 2040: break

    _cal_cache = months
    logger.info("Takvim hazir.")
    return _cal_cache

# 👇 ASYNC SAFE WRAPPER
async def get_cal():
    global _cal_cache
    if _cal_cache:
        return _cal_cache
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, build_cal)

# ================= COMMANDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "HICRI TAKVIM BOTU V2\n\n/bugun\n/analiz\n/karsilastir 2025"
    )

async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hesaplanıyor...")

    await get_cal()

    today = datetime.now(timezone.utc).date()
    gun, ay, _, hyil = hicri(today)

    await update.message.reply_text(
        f"Bugun: {today}\nHicri: {gun} {ay} {hyil}"
    )

# diğer handlerlar aynen kalabilir...

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bugun", bugun))

    logger.info("Bot basladi (hesaplama yok)")

    app.run_polling()

if __name__ == "__main__":
    main()