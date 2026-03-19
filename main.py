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
# NEW MOONS
# =========================
def get_new_moons():
    t0 = ts.utc(2000,1,1)
    t1 = ts.utc(2035,12,31)

    times, phases = find_discrete(t0, t1, moon_phases(eph))

    return [
        t.utc_datetime().replace(tzinfo=timezone.utc)
        for t,p in zip(times, phases)
        if p == 0
    ]

NEW_MOONS = get_new_moons()

# =========================
# HİLAL GÖRÜNÜRLÜK
# =========================
def hilal_visible(date, nm):

    t = ts.utc(date.year, date.month, date.day, 18)

    loc = earth + Topos(21.4,39.8)

    e = loc.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    alt, _, _ = m.altaz()
    elong = m.separation_from(s).degrees

    age = (datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc) - nm).total_seconds()/3600

    return alt.degrees > 5 and elong > 8 and age > 12

# =========================
# AY BAŞLANGIÇ
# =========================
def get_month_starts():

    starts = []

    for nm in NEW_MOONS:

        for i in [1,2,3]:

            d = (nm + timedelta(days=i)).date()

            if hilal_visible(d, nm):
                starts.append(d)
                break
        else:
            starts.append((nm + timedelta(days=2)).date())

    return sorted(starts)

MONTHS = get_month_starts()

# =========================
# AY İSİMLERİ
# =========================
AYLAR = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep",
    "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
]

# =========================
# ANCHOR (SADECE 1 NOKTA)
# =========================
ANCHOR_DATE = datetime(2025,3,1).date()

ANCHOR_INDEX = min(range(len(MONTHS)),
                   key=lambda i: abs((MONTHS[i]-ANCHOR_DATE).days))

# =========================
# HİCRİ HESAP
# =========================
def get_hijri(date):

    idx = None

    for i,m in enumerate(MONTHS):
        if m <= date:
            idx = i

    diff = idx - ANCHOR_INDEX

    ay = (8 + diff) % 12
    start = MONTHS[idx]

    gun = (date - start).days + 1

    return gun, AYLAR[ay]

# =========================
# YIL ANALİZ
# =========================
def analyze_year(year):

    ramazan = None
    zilhicce = None

    for i,m in enumerate(MONTHS):

        diff = i - ANCHOR_INDEX
        ay = (8 + diff) % 12

        if ay == 8 and m.year == year:
            ramazan = m

        if ay == 11 and m.year == year:
            zilhicce = m

    return {
        "ramazan": ramazan,
        "bayram": ramazan + timedelta(days=29),
        "arefe": zilhicce + timedelta(days=8),
        "kurban": zilhicce + timedelta(days=9)
    }

# =========================
# BOT
# =========================
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()
    g,a = get_hijri(today)

    await update.message.reply_text(f"📅 {today}\nHicri: {g} {a}")

async def yil(update: Update, context: ContextTypes.DEFAULT_TYPE):

    y = int(context.args[0])
    d = analyze_year(y)

    text = f"{y}\nRamazan: {d['ramazan']}\nBayram: {d['bayram']}\nArefe: {d['arefe']}"
    await update.message.reply_text(text)

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("yil", yil))

print("🚀 GERÇEK HİLAL MOTOR AKTİF")
app.run_polling()
