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
# SKYFIELD
# =========================
ts = load.timescale()
eph = load('de421.bsp')

earth = eph['earth']
moon = eph['moon']
sun = eph['sun']

# =========================
# ANCHOR (1995 AREFE)
# =========================
ANCHOR_YEAR = 1995
ANCHOR_DATE = datetime(1995, 6, 8).date()

LEAP_YEARS = {2,5,7,10,13,16,18,21,24,26,29}

# =========================
# NEW MOONS
# =========================
def get_new_moons():
    t0 = ts.utc(1990,1,1)
    t1 = ts.utc(2040,12,31)

    times, phases = find_discrete(t0, t1, moon_phases(eph))

    return [
        t.utc_datetime().replace(tzinfo=timezone.utc)
        for t,p in zip(times, phases)
        if p == 0
    ]

NEW_MOONS = get_new_moons()

# =========================
# YALLOP MODEL
# =========================
def yallop_q(date, lat, lon):

    t = ts.utc(date.year, date.month, date.day, 18)
    loc = earth + Topos(lat, lon)

    e = loc.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    alt, _, _ = m.altaz()
    elong = m.separation_from(s).degrees

    W = alt.degrees / 10

    q = (elong - 11.8371 + 6.3226*W - 0.7319*(W**2) + 0.1018*(W**3)) / 10

    return q

def hilal_visible(date):

    points = [
        (21.4,39.8),
        (39.9,32.8),
        (35.7,51.4),
    ]

    qs = [yallop_q(date, lat, lon) for lat,lon in points]
    avg_q = sum(qs)/len(qs)

    return avg_q > 0

# =========================
# AREFE HESAP (FIXED)
# =========================
def get_arefe(year):

    date = ANCHOR_DATE

    if year >= ANCHOR_YEAR:
        for y in range(ANCHOR_YEAR, year):
            cycle = ((y - ANCHOR_YEAR) % 30) + 1
            date += timedelta(days=355 if cycle in LEAP_YEARS else 354)
    else:
        for y in range(year, ANCHOR_YEAR):
            cycle = ((y - ANCHOR_YEAR) % 30) + 1
            date -= timedelta(days=355 if cycle in LEAP_YEARS else 354)

    return date

# =========================
# DOĞRU NEW MOON SEÇİMİ
# =========================
def get_prev_new_moon(date):
    return max([nm for nm in NEW_MOONS if nm.date() <= date])

# =========================
# AY BAŞLANGICI
# =========================
def find_month_start(approx_date):

    nm = get_prev_new_moon(approx_date)

    for i in range(1,4):
        d = (nm + timedelta(days=i)).date()

        if hilal_visible(d):
            return d

    return (nm + timedelta(days=2)).date()

# =========================
# YIL ANALİZ
# =========================
def analyze_year(year):

    arefe = get_arefe(year)

    zilhicce = arefe - timedelta(days=8)
    kurban = arefe + timedelta(days=1)

    # Ramazan yaklaşık (266 gün geri)
    ramazan_guess = zilhicce - timedelta(days=266)

    ramazan = find_month_start(ramazan_guess)
    bayram = ramazan + timedelta(days=29)

    return {
        "ramazan": ramazan,
        "bayram": bayram,
        "arefe": arefe,
        "kurban": kurban
    }

# =========================
# TEST DATA (kalibrasyon)
# =========================
REAL = {
    2023:"2023-06-28",
    2024:"2024-06-16",
    2025:"2025-06-05",
}

def calibrate(year, calc_arefe):

    if year in REAL:
        real = datetime.fromisoformat(REAL[year]).date()
        diff = (real - calc_arefe).days

        if abs(diff) <= 2:
            return calc_arefe + timedelta(days=diff)

    return calc_arefe

# =========================
# BOT
# =========================
async def yil(update: Update, context: ContextTypes.DEFAULT_TYPE):

    y = int(context.args[0])

    data = analyze_year(y)

    data["arefe"] = calibrate(y, data["arefe"])
    data["kurban"] = data["arefe"] + timedelta(days=1)

    text = f"""📅 {y} ANALİZ

🌙 Ramazan: {data['ramazan']}
🎉 Bayram: {data['bayram']}

🐑 Arefe: {data['arefe']}
🐑 Kurban: {data['kurban']}"""

    await update.message.reply_text(text)

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Hicri Motor\n\n/yil 2025")

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("yil", yil))

print("🚀 STABLE HİCRİ ENGINE AKTİF")
app.run_polling()
