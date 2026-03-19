import os
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 🌙 Astronomi
from skyfield.api import load, Topos

# 🔐 TOKEN
TOKEN = os.getenv("TOKEN")

logging.basicConfig(level=logging.INFO)

# 🌍 Skyfield yükle
ts = load.timescale()
eph = load('de421.bsp')

earth = eph['earth']
moon = eph['moon']
sun = eph['sun']

# 🚀 START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 Hilal Takvim Bot (NASA MODE)\n\n"
        "/dunya → Global hilal analizi\n"
        "/konum istanbul → Şehir bazlı analiz"
    )

# 🌍 NASA GLOBAL ANALİZ
async def dunya(update: Update, context: ContextTypes.DEFAULT_TYPE):

    t = ts.now()

    e = earth.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    elongation = m.separation_from(s).degrees

    mesaj = "🌍 NASA HİLAL ANALİZİ\n\n"
    mesaj += f"🌙 Elongation: {elongation:.2f}°\n\n"

    if elongation < 7:
        mesaj += "❌ Hilal dünya genelinde görünmez"
        await update.message.reply_text(mesaj)
        return

    locations = {
        "Sudan 🇸🇩": (15.5, 32.5),
        "Mekke 🇸🇦": (21.39, 39.86),
        "Türkiye 🇹🇷": (39.0, 35.0),
        "İran 🇮🇷": (35.0, 51.0),
        "Afganistan 🇦🇫": (34.5, 69.2),
    }

    mesaj += "🌍 GÖRÜNÜRLÜK:\n\n"

    for name, (lat, lon) in locations.items():
        loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)
        alt, az, dist = loc.at(t).observe(moon).apparent().altaz()

        altitude = alt.degrees

        mesaj += f"{name}\n"
        mesaj += f"🌙 Yükseklik: {altitude:.2f}°\n"

        if altitude < 0:
            mesaj += "❌ Görünmez\n\n"
        elif altitude < 5:
            mesaj += "⚠️ Çok zor\n\n"
        elif altitude < 10:
            mesaj += "⚠️ Zor\n\n"
        else:
            mesaj += "✅ Görülebilir\n\n"

    await update.message.reply_text(mesaj)

# 🌍 ŞEHİR BAZLI (NASA)
async def konum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sehir = " ".join(context.args).lower()

        cities = {
            "istanbul": (41.01, 28.97),
            "ankara": (39.93, 32.85),
            "izmir": (38.42, 27.14),
            "mekke": (21.39, 39.86),
            "medine": (24.47, 39.61),
            "cidde": (21.54, 39.17),
        }

        if sehir not in cities:
            await update.message.reply_text("❌ Şehir bulunamadı")
            return

        lat, lon = cities[sehir]

        t = ts.now()
        loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)

        alt, az, dist = loc.at(t).observe(moon).apparent().altaz()
        altitude = alt.degrees

        mesaj = f"🌍 {sehir.upper()} NASA ANALİZ\n\n"
        mesaj += f"🌙 Ay yüksekliği: {altitude:.2f}°\n\n"

        if altitude < 0:
            mesaj += "❌ Görünmez"
        elif altitude < 5:
            mesaj += "⚠️ Çok zor"
        elif altitude < 10:
            mesaj += "⚠️ Zor"
        else:
            mesaj += "✅ Görülebilir"

        await update.message.reply_text(mesaj)

    except:
        await update.message.reply_text("❌ Hata oluştu")

# 🚀 APP
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("dunya", dunya))
app.add_handler(CommandHandler("konum", konum))

print("Bot çalışıyor...")
app.run_polling()
