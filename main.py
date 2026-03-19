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
# ŞEHİRLER
# =========================
CITIES = {
    "istanbul": (41.01, 28.97),
    "ankara": (39.93, 32.85),
    "izmir": (38.42, 27.14),
    "mekke": (21.39, 39.86),
    "medine": (24.47, 39.61),
    "cidde": (21.54, 39.17),
    "tahran": (35.68, 51.41),
    "kabil": (34.55, 69.20),
}

# =========================
# GRID
# =========================
GRID = {
    "Amerika": (0, -70),
    "Afrika": (15, 30),
    "Türkiye": (39, 35),
    "Suudi": (21, 39),
    "İran": (35, 51),
    "Afganistan": (34, 65),
}

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
def hilal_param(date, lat, lon, hour=18):
    t = ts.utc(date.year, date.month, date.day, hour)

    loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)

    e = loc.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    alt, _, _ = m.altaz()
    elong = m.separation_from(s).degrees

    return alt.degrees, elong

# =========================
# SKOR (GELİŞMİŞ)
# =========================
def score(alt, elong):
    return (alt * 0.6) + (elong * 0.4)

def label(s):
    if s < 5:
        return "❌"
    elif s < 8:
        return "⚠️"
    else:
        return "✅"

# =========================
# GLOBAL ANALİZ
# =========================
def global_analysis(date):

    best = ("", -999)
    data = []

    for name, (lat, lon) in GRID.items():

        alt, elong = hilal_param(date, lat, lon)
        s = score(alt, elong)

        data.append((name, alt, elong, s))

        if s > best[1]:
            best = (name, s)

    return data, best

# =========================
# ŞEHİR ANALİZ (SAATLİ)
# =========================
def city_analysis(city, date):

    lat, lon = CITIES[city]

    best_hour = None
    best_score = -999

    for h in range(15, 21):

        alt, elong = hilal_param(date, lat, lon, h)
        s = score(alt, elong)

        if s > best_score:
            best_score = s
            best_hour = h

    return best_hour, best_score

# =========================
# HİLAL KOMUTU
# =========================
async def hilal(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()

    data, best = global_analysis(today)

    text = "🌙 HİLAL ANALİZ\n\n"

    for name, alt, elong, s in data:
        text += f"{name}: {label(s)} ({s:.1f})\n"

    text += f"\n🌍 İlk güçlü bölge: {best[0]}"

    await update.message.reply_text(text)

# =========================
# ŞEHİR KOMUTU
# =========================
async def sehir(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        city = context.args[0].lower()
    except:
        await update.message.reply_text("Kullanım: /sehir istanbul")
        return

    if city not in CITIES:
        await update.message.reply_text("Şehir yok")
        return

    today = datetime.now(timezone.utc).date()

    hour, s = city_analysis(city, today)

    await update.message.reply_text(
        f"🌙 {city.upper()}\n\n"
        f"⏰ En iyi saat: {hour}:00 UTC\n"
        f"Durum: {label(s)} ({s:.1f})"
    )

# =========================
# 3 GÜN
# =========================
async def hilal_3gun(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()

    text = "🌙 3 GÜN ANALİZ\n\n"

    for i, label_txt in [(-1, "Dün"), (0, "Bugün"), (1, "Yarın")]:

        d = today + timedelta(days=i)
        _, best = global_analysis(d)

        text += f"{label_txt}: {best[0]}\n"

    await update.message.reply_text(text)

# =========================
# HARİTA
# =========================
async def harita(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()

    data, _ = global_analysis(today)

    text = "🗺️ HARİTA\n\n"

    for name, _, _, s in data:
        text += f"{name}: {label(s)}\n"

    await update.message.reply_text(text)

# =========================
# BAYRAM AI
# =========================
async def bayram(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()

    _, best_today = global_analysis(today)
    _, best_tomorrow = global_analysis(today + timedelta(days=1))

    if best_today[1] > 8:
        msg = "🎉 Yarın bayram olabilir"
    elif best_tomorrow[1] > 8:
        msg = "🎉 Bayram 2 gün sonra"
    else:
        msg = "❌ Henüz değil"

    await update.message.reply_text(msg)

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 V5 PRO HİLAL SİSTEMİ\n\n"
        "/hilal\n"
        "/sehir istanbul\n"
        "/hilal_3gun\n"
        "/harita\n"
        "/bayram"
    )

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("hilal", hilal))
app.add_handler(CommandHandler("sehir", sehir))
app.add_handler(CommandHandler("hilal_3gun", hilal_3gun))
app.add_handler(CommandHandler("harita", harita))
app.add_handler(CommandHandler("bayram", bayram))

print("🚀 V5 PRO AKTİF")
app.run_polling()
