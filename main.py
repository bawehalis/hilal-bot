import os
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from skyfield.api import load, Topos
from skyfield.almanac import find_discrete, moon_phases

# =========================
TOKEN = os.getenv("TOKEN")
logging.basicConfig(level=logging.INFO)

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
# HİLAL PARAMETRE
# =========================
def hilal_param(date, lat=21.4, lon=39.8, hour=18):

    t = ts.utc(date.year, date.month, date.day, hour)

    loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)

    e = loc.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    alt, _, _ = m.altaz()
    elong = m.separation_from(s).degrees

    return alt.degrees, elong

# =========================
# HİLAL GÖRÜNÜRLÜK (GERÇEK MODEL)
# =========================
def hilal_visible(alt, elong, age):

    if alt < 0 or elong < 6 or age < 12:
        return False

    score = (alt * 0.4) + (elong * 0.4) + (age * 0.2)

    return score > 10

# =========================
# AY BAŞLANGICI (AKILLI)
# =========================
def choose_month_start(nm):

    for i in range(1, 4):  # 1-3 gün dene

        date = (nm + timedelta(days=i)).date()

        alt, elong = hilal_param(date)

        age = (datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc) - nm).total_seconds() / 3600

        if hilal_visible(alt, elong, age):
            return date

    return (nm + timedelta(days=2)).date()

# =========================
# TÜM AYLAR
# =========================
MONTHS = sorted([choose_month_start(nm) for nm in NEW_MOONS])

AYLAR = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep",
    "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
]

# =========================
# ANCHOR (RAMAZAN SABİT)
# =========================
ANCHOR = datetime(2025, 3, 1).date()

ANCHOR_INDEX = min(range(len(MONTHS)),
                   key=lambda i: abs((MONTHS[i] - ANCHOR).days))

# =========================
# AY INDEX
# =========================
def ay_index(i):
    return (i - ANCHOR_INDEX + 11) % 12

# =========================
# HİCRİ TARİH
# =========================
def get_hijri(date):

    idx = None

    for i, m in enumerate(MONTHS):
        if m <= date:
            idx = i

    if idx is None:
        return 0, "?"

    start = MONTHS[idx]
    next_m = MONTHS[idx + 1] if idx + 1 < len(MONTHS) else start + timedelta(days=30)

    gun = (date - start).days + 1
    ay = ay_index(idx)

    return gun, AYLAR[ay], start, next_m

# =========================
# YIL ANALİZ (DOĞRU MODEL)
# =========================
def analyze_year(year):

    target = datetime(year, 6, 1).date()

    ramazan_list = []
    zilhicce_list = []

    for i, m in enumerate(MONTHS):

        ay = ay_index(i)

        if ay == 8:
            ramazan_list.append(m)

        if ay == 11:
            zilhicce_list.append(m)

    if not ramazan_list or not zilhicce_list:
        return None

    ramazan = min(ramazan_list, key=lambda x: abs(x - target))
    zilhicce = min(zilhicce_list, key=lambda x: abs(x - target))

    # 🔥 29 / 30 OTOMATİK KARAR
    next_ramazan = min([m for m in ramazan_list if m > ramazan], default=ramazan + timedelta(days=30))
    ramazan_length = (next_ramazan - ramazan).days

    return {
        "ramazan": ramazan,
        "ramazan_bayram": ramazan + timedelta(days=ramazan_length),
        "arefe": zilhicce + timedelta(days=8),
        "kurban": zilhicce + timedelta(days=9)
    }

# =========================
# BOT KOMUTLARI
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 ULTIMATE HİLAL MOTOR\n\n"
        "/bugun\n"
        "/yil 2025"
    )

async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()

    gun, ay, _, _ = get_hijri(today)

    await update.message.reply_text(
        f"📅 Bugün\n\nMiladi: {today}\nHicri: {gun} {ay}"
    )

async def yil(update: Update, context: ContextTypes.DEFAULT_TYPE):

    year = int(context.args[0])

    data = analyze_year(year)

    if not data:
        await update.message.reply_text("Veri yok")
        return

    text = f"📅 {year} ANALİZ\n\n"
    text += f"🌙 Ramazan: {data['ramazan']}\n"
    text += f"🎉 Bayram: {data['ramazan_bayram']}\n\n"
    text += f"🐑 Arefe: {data['arefe']}\n"
    text += f"🐑 Bayram: {data['kurban']}"

    await update.message.reply_text(text)

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("yil", yil))

print("🚀 ULTIMATE AKTİF")
app.run_polling()
