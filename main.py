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
    t0 = ts.utc(2000, 1, 1)
    t1 = ts.utc(2035, 12, 31)

    times, phases = find_discrete(t0, t1, moon_phases(eph))

    return [
        t.utc_datetime().replace(tzinfo=timezone.utc)
        for t, p in zip(times, phases)
        if p == 0
    ]

NEW_MOONS = get_new_moons()

# =========================
# HİLAL MODEL
# =========================
def visible(date, nm):

    t = ts.utc(date.year, date.month, date.day, 18)

    loc = earth + Topos(latitude_degrees=21.4, longitude_degrees=39.8)

    e = loc.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    alt, _, _ = m.altaz()
    elong = m.separation_from(s).degrees

    age = (datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc) - nm).total_seconds()/3600

    if alt.degrees < 0 or elong < 6 or age < 12:
        return False

    score = alt.degrees*0.4 + elong*0.4 + age*0.2

    return score > 10

# =========================
# AY BAŞLANGIÇ
# =========================
def get_month_starts():

    starts = []

    for nm in NEW_MOONS:

        for i in range(1,4):
            d = (nm + timedelta(days=i)).date()

            if visible(d, nm):
                starts.append(d)
                break
        else:
            starts.append((nm + timedelta(days=2)).date())

    return sorted(starts)

MONTHS = get_month_starts()

# =========================
# HİCRİ AYLAR
# =========================
AYLAR = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep",
    "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
]

# =========================
# ANCHOR (DOĞRU NOKTA)
# =========================
ANCHOR_DATE = datetime(2025,3,1).date()

ANCHOR_INDEX = min(range(len(MONTHS)),
                   key=lambda i: abs((MONTHS[i]-ANCHOR_DATE).days))

# =========================
# HİCRİ BUL
# =========================
def get_hijri(date):

    idx = None

    for i,m in enumerate(MONTHS):
        if m <= date:
            idx = i

    if idx is None:
        return 0,"?"

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

    if not ramazan:
        ramazan = min(MONTHS, key=lambda x: abs(x - datetime(year,3,1).date()))

    if not zilhicce:
        zilhicce = min(MONTHS, key=lambda x: abs(x - datetime(year,6,1).date()))

    return {
        "ramazan": ramazan,
        "bayram": ramazan + timedelta(days=29),
        "arefe": zilhicce + timedelta(days=8),
        "kurban": zilhicce + timedelta(days=9)
    }

# =========================
# KOMUTLAR
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 HİLAL MOTOR AKTİF\n\n"
        "/bugun\n"
        "/yil 2025\n"
        "/hilal"
    )

async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()
    g,a = get_hijri(today)

    await update.message.reply_text(
        f"📅 Bugün\n\nMiladi: {today}\nHicri: {g} {a}"
    )

async def yil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    y = int(context.args[0])
    d = analyze_year(y)

    await update.message.reply_text(
        f"📅 {y}\n\n"
        f"🌙 Ramazan: {d['ramazan']}\n"
        f"🎉 Bayram: {d['bayram']}\n\n"
        f"🐑 Arefe: {d['arefe']}\n"
        f"🐑 Kurban: {d['kurban']}"
    )

async def hilal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()

    alt, elong = 0,0
    t = ts.utc(today.year, today.month, today.day, 18)

    loc = earth + Topos(latitude_degrees=39, longitude_degrees=35)
    e = loc.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    alt,_,_ = m.altaz()
    elong = m.separation_from(s).degrees

    await update.message.reply_text(
        f"🌙 Hilal Analizi\n\n"
        f"Yükseklik: {alt.degrees:.2f}\n"
        f"Elongation: {elong:.2f}"
    )

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("yil", yil))
app.add_handler(CommandHandler("hilal", hilal))

print("🚀 SİSTEM TAM AKTİF")
app.run_polling()
