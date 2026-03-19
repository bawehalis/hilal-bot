import os
import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 🌙 Astronomi
from skyfield.api import load, Topos

TOKEN = os.getenv("TOKEN")

logging.basicConfig(level=logging.INFO)

# 🌍 Skyfield
ts = load.timescale()
eph = load('de421.bsp')

earth = eph['earth']
moon = eph['moon']
sun = eph['sun']

# 📅 Basit hicri approx
months = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep","Şaban",
    "Ramazan","Şevval","Zilkade","Zilhicce"
]

def gregorian_to_hijri(now):
    base = datetime(2024, 7, 7, tzinfo=timezone.utc)
    days = (now - base).days
    hy = 1446 + days // 354
    hm = ((days % 354) // 29) + 1
    hd = ((days % 354) % 29) + 1
    return hy, hm, hd

# 🚀 START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 Hilal Takvim Bot PRO (NASA)\n\n"
        "/bugun → Günlük durum\n"
        "/hilal → Hilal analizi\n"
        "/dunya → Global analiz\n"
        "/konum şehir → Şehir analizi\n"
        "/arefe → Arefe mi?\n"
        "/ramazan → Ramazan mı?"
    )

# 📅 BUGÜN
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone.utc)
    hy, hm, hd = gregorian_to_hijri(now)

    mesaj = f"📅 BUGÜN\n\n"
    mesaj += f"Miladi: {now.date()}\n"
    mesaj += f"Hicri: {hd} {months[hm-1]} {hy}\n\n"

    if hm == 12 and hd == 9:
        mesaj += "🕋 Arefe günü"
    elif hm == 9:
        mesaj += "🌙 Ramazan ayı"
    else:
        mesaj += "Normal gün"

    await update.message.reply_text(mesaj)

# 🌙 HİLAL (NASA)
async def hilal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = ts.now()

    e = earth.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    elongation = m.separation_from(s).degrees

    mesaj = "🌙 HİLAL ANALİZİ\n\n"
    mesaj += f"Elongation: {elongation:.2f}°\n\n"

    if elongation < 7:
        mesaj += "❌ Hilal görünmez"
    elif elongation < 10:
        mesaj += "⚠️ Çok zor"
    elif elongation < 15:
        mesaj += "⚠️ Zor"
    else:
        mesaj += "✅ Görülebilir"

    await update.message.reply_text(mesaj)

# 🌍 GLOBAL (NASA)
async def dunya(update: Update, context: ContextTypes.DEFAULT_TYPE):

    t = ts.now()
    e = earth.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    elongation = m.separation_from(s).degrees

    mesaj = "🌍 GLOBAL HİLAL ANALİZİ\n\n"
    mesaj += f"Elongation: {elongation:.2f}°\n\n"

    if elongation < 7:
        mesaj += "❌ Dünya genelinde görünmez"
        await update.message.reply_text(mesaj)
        return

    locations = {
        "Sudan 🇸🇩": (15.5, 32.5),
        "Mekke 🇸🇦": (21.39, 39.86),
        "Türkiye 🇹🇷": (39.0, 35.0),
        "İran 🇮🇷": (35.0, 51.0),
        "Afganistan 🇦🇫": (34.5, 69.2),
    }

    for name, (lat, lon) in locations.items():
        loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)
        alt, az, dist = loc.at(t).observe(moon).apparent().altaz()

        altitude = alt.degrees

        mesaj += f"{name}\n"
        mesaj += f"Yükseklik: {altitude:.2f}°\n"

        if altitude < 0:
            mesaj += "❌ Görünmez\n\n"
        elif altitude < 5:
            mesaj += "⚠️ Çok zor\n\n"
        elif altitude < 10:
            mesaj += "⚠️ Zor\n\n"
        else:
            mesaj += "✅ Görülebilir\n\n"

    await update.message.reply_text(mesaj)

# 🌍 ŞEHİR
async def konum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sehir = " ".join(context.args).lower()

        cities = {
            # 🇹🇷
            "istanbul": (41.01, 28.97),
            "ankara": (39.93, 32.85),
            "izmir": (38.42, 27.14),
            "bursa": (40.19, 29.06),
            "antalya": (36.88, 30.70),
            "batman": (37.88, 41.13),

            # 🇸🇦
            "mekke": (21.39, 39.86),
            "medine": (24.47, 39.61),
            "cidde": (21.54, 39.17),
            "riyad": (24.71, 46.67),
        }

        if sehir not in cities:
            await update.message.reply_text("❌ Şehir bulunamadı")
            return

        lat, lon = cities[sehir]

        t = ts.now()
        loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)

        alt, az, dist = loc.at(t).observe(moon).apparent().altaz()
        altitude = alt.degrees

        mesaj = f"🌍 {sehir.upper()}\n\n"
        mesaj += f"Ay yüksekliği: {altitude:.2f}°\n\n"

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

# 🕋 AREFE
async def arefe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone.utc)
    hy, hm, hd = gregorian_to_hijri(now)

    if hm == 12 and hd == 9:
        await update.message.reply_text("🕋 Bugün arefe")
    else:
        await update.message.reply_text("❌ Bugün arefe değil")

# 🌙 RAMAZAN
async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone.utc)
    hy, hm, hd = gregorian_to_hijri(now)

    if hm == 9:
        await update.message.reply_text("🌙 Ramazan ayındasın")
    else:
        await update.message.reply_text("Ramazan değil")

# 🚀 APP
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("hilal", hilal))
app.add_handler(CommandHandler("dunya", dunya))
app.add_handler(CommandHandler("konum", konum))
app.add_handler(CommandHandler("arefe", arefe))
app.add_handler(CommandHandler("ramazan", ramazan))

print("Bot çalışıyor...")
app.run_polling()
