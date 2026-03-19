import os
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from skyfield.api import load, Topos
from skyfield.almanac import find_discrete, moon_phases

TOKEN = os.getenv("TOKEN")
logging.basicConfig(level=logging.INFO)

# =========================
# DATASET
# =========================
REAL_DATA = {
    2000: "2000-11-27",
    2001: "2001-11-17",
    2002: "2002-11-06",
    2003: "2003-10-27",
    2004: "2004-10-16",
    2005: "2005-10-05",
    2006: "2006-09-24",
    2007: "2007-09-13",
    2008: "2008-09-01",
    2009: "2009-08-22",
    2010: "2010-08-12",
    2011: "2011-08-01",
    2012: "2012-07-21",
    2013: "2013-07-10",
    2014: "2014-06-29",
    2015: "2015-06-18",
    2016: "2016-06-06",
    2017: "2017-05-27",
    2018: "2018-05-17",
    2019: "2019-05-06",
    2020: "2020-04-24",
    2021: "2021-04-13",
    2022: "2022-04-02",
    2023: "2023-03-23",
    2024: "2024-03-11",
    2025: "2025-03-01",
}

# =========================
# ASTRONOMİ
# =========================
ts = load.timescale()
eph = load('de421.bsp')

earth = eph['earth']
moon = eph['moon']
sun = eph['sun']

# =========================
# NEW MOON
# =========================
def get_new_moons():
    t0 = ts.utc(1995, 1, 1)
    t1 = ts.utc(2035, 12, 31)

    times, phases = find_discrete(t0, t1, moon_phases(eph))

    return [
        t.utc_datetime().replace(tzinfo=timezone.utc)
        for t, p in zip(times, phases)
        if p == 0
    ]

NEW_MOONS = get_new_moons()

# =========================
# PARAM
# =========================
def hilal_param(date, lat=20, lon=30):
    t = ts.utc(date.year, date.month, date.day, 18)

    loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)

    e = loc.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    alt, _, _ = m.altaz()
    elong = m.separation_from(s).degrees

    return alt.degrees, elong

# =========================
# SKOR
# =========================
def score(alt, elong):
    return (alt * 0.6) + (elong * 0.4)

# =========================
# CALIBRATION
# =========================
def auto_calibrate():

    best_t = 6.5
    best_err = 999

    for t in [5.5, 6, 6.5, 7, 7.5]:

        err = 0

        for year, real_str in REAL_DATA.items():

            real = datetime.fromisoformat(real_str).date()

            for nm in NEW_MOONS:
                if nm.year == year:

                    d1 = (nm + timedelta(days=1)).date()
                    s1 = score(*hilal_param(d1))

                    model = d1 if s1 > t else (nm + timedelta(days=2)).date()

                    err += abs((model - real).days)
                    break

        if err < best_err:
            best_err = err
            best_t = t

    return best_t

THRESHOLD = auto_calibrate()

# =========================
# AY BAŞLANGIÇ
# =========================
def choose_day(nm):

    d1 = (nm + timedelta(days=1)).date()
    d2 = (nm + timedelta(days=2)).date()

    s1 = score(*hilal_param(d1))

    return d1 if s1 > THRESHOLD else d2

MONTHS = sorted([choose_day(nm) for nm in NEW_MOONS])

AYLAR = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep",
    "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
]

# =========================
# ANCHOR (RAMAZAN REFERANS)
# =========================
ANCHOR = datetime(2025, 3, 1).date()  # RAMAZAN BAŞI

ANCHOR_INDEX = min(range(len(MONTHS)),
                   key=lambda i: abs((MONTHS[i] - ANCHOR).days))

# =========================
# HİCRİ (FIX)
# =========================
def get_hijri(date):

    idx = None

    for i, m in enumerate(MONTHS):
        if m <= date:
            idx = i

    if idx is None:
        return "?", "?", None, None, None

    start = MONTHS[idx]
    next_m = MONTHS[idx + 1] if idx + 1 < len(MONTHS) else start + timedelta(days=29)

    gun = (date - start).days + 1

    # 🔥 DÜZELTME
    ay = (idx - ANCHOR_INDEX) % 12

    return gun, AYLAR[ay], idx, start, next_m

# =========================
# BOT
# =========================
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()
    gun, ay, _, _, _ = get_hijri(today)

    await update.message.reply_text(
        f"📅 Bugün\n\nMiladi: {today}\nHicri: {gun} {ay}"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 DÜZELTİLDİ\n\n/bugun")

# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))

print(f"🚀 AKTİF (threshold={THRESHOLD})")
app.run_polling()
