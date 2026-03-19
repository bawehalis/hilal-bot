import os
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from skyfield.api import load, Topos
import matplotlib.pyplot as plt

# 🔐 TOKEN
TOKEN = os.getenv("TOKEN")

logging.basicConfig(level=logging.INFO)

# 🌍 Skyfield yükle
ts = load.timescale()
eph = load('de421.bsp')

earth = eph['earth']
moon = eph['moon']
sun = eph['sun']

# 🌙 elongation hesap
def elongation(t):
    e = earth.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()
    return m.separation_from(s).degrees

# 🌙 görünürlük fonksiyonu
def visibility(lat, lon, date):
    t = ts.utc(date.year, date.month, date.day, 18)

    loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)
    alt, az, dist = loc.at(t).observe(moon).apparent().altaz()

    alt = alt.degrees
    el = elongation(t)

    if el < 7 or alt < 0:
        return 0  # görünmez
    elif alt < 5:
        return 1  # çok zor
    elif alt < 10:
        return 2  # zor
    else:
        return 3  # görünür

# 🌍 HARİTA OLUŞTUR
def generate_map(date):
    lats = []
    lons = []
    colors = []

    for lat in range(-60, 61, 5):
        for lon in range(-180, 181, 5):
            v = visibility(lat, lon, date)

            lats.append(lat)
            lons.append(lon)

            if v == 0:
                colors.append("black")
            elif v == 1:
                colors.append("red")
            elif v == 2:
                colors.append("orange")
            else:
                colors.append("green")

    plt.figure(figsize=(12,6))
    plt.scatter(lons, lats, c=colors, s=10)

    plt.title("Hilal Görünürlük Haritası")
    plt.xlabel("Longitude")
    plt.ylabel("Latitude")

    file = "/tmp/hilal_map.png"
    plt.savefig(file)
    plt.close()

    return file

# 🌍 ÜLKE ANALİZİ
def country_analysis(date):
    countries = {
        "🇸🇦 Suudi Arabistan": (21.4, 39.8),
        "🇹🇷 Türkiye": (39.0, 35.0),
        "🇮🇷 İran": (35.0, 51.0),
        "🇦🇫 Afganistan": (34.5, 69.2),
    }

    result = ""

    for name, (lat, lon) in countries.items():
        v = visibility(lat, lon, date)

        if v == 0:
            durum = "❌ Görünmez"
        elif v == 1:
            durum = "⚠️ Çok zor"
        elif v == 2:
            durum = "⚠️ Zor"
        else:
            durum = "✅ Görülebilir"

        result += f"{name}: {durum}\n"

    return result

# 🚀 /harita
async def harita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = datetime.now(timezone.utc).date()
    file = generate_map(date)

    await update.message.reply_photo(photo=open(file, "rb"))

# 🚀 /ulke
async def ulke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = datetime.now(timezone.utc).date()
    msg = "🌍 ÜLKE ANALİZİ\n\n"
    msg += country_analysis(date)

    await update.message.reply_text(msg)

# 🚀 /hilal
async def hilal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = datetime.now(timezone.utc).date()

    v = visibility(21.4, 39.8, date)

    if v == 0:
        msg = "❌ Hilal görünmez"
    elif v == 1:
        msg = "⚠️ Çok zor"
    elif v == 2:
        msg = "⚠️ Zor"
    else:
        msg = "✅ Hilal görülebilir"

    await update.message.reply_text(msg)

# 🚀 START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 HİLAL ANALİZ BOTU\n\n"
        "/harita → dünya haritası\n"
        "/ulke → ülke analizi\n"
        "/hilal → genel durum"
    )

# 🚀 APP
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("harita", harita))
app.add_handler(CommandHandler("ulke", ulke))
app.add_handler(CommandHandler("hilal", hilal))

print("Bot aktif 🚀")
app.run_polling()
