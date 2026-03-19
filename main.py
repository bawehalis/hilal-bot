import logging
from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

import ephem
from astral import LocationInfo
from astral.sun import sun

# 🔐 TOKEN Railway'den geliyor
import os
TOKEN = os.getenv("TOKEN")

logging.basicConfig(level=logging.INFO)

# 🌙 AY YAŞI HESABI (basit ama yeterli)
def moon_age(now):
    new_moon = datetime(2024, 1, 11, tzinfo=timezone.utc)
    diff = now - new_moon
    return (diff.total_seconds() / 86400) % 29.53

# 📅 HİCRİ (basit model)
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
    mesaj = (
        "🌙 Hilal Takvim Bot PRO\n\n"
        "/bugun → Günlük durum\n"
        "/hilal → Hilal analizi\n"
        "/dunya → Global rapor\n"
        "/konum izmir → Şehre göre hilal\n"
        "/arefe → Arefe mi?\n"
        "/ramazan → Ramazan bilgisi"
    )
    await update.message.reply_text(mesaj)

# 📅 BUGÜN
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone.utc)
    hy, hm, hd = gregorian_to_hijri(now)

    mesaj = f"📅 BUGÜN\n\n"
    mesaj += f"Miladi: {now.date()}\n"
    mesaj += f"Hicri: {hd} {months[hm-1]} {hy}\n\n"

    if hm == 12 and hd == 9:
        mesaj += "🕋 Arefe günü\n"
    elif hm == 9:
        mesaj += "🌙 Ramazan\n"
    else:
        mesaj += "Normal gün"

    await update.message.reply_text(mesaj)

# 🌙 HİLAL
async def hilal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone.utc)
    age = moon_age(now)

    mesaj = f"🌙 HİLAL\n\n"
    mesaj += f"Ay yaşı: {age:.2f} gün\n\n"

    if age < 1:
        mesaj += "❌ Görünmez"
    elif age < 1.5:
        mesaj += "⚠️ Çok zor"
    elif age < 2:
        mesaj += "⚠️ Zor"
    else:
        mesaj += "✅ Görülebilir"

    await update.message.reply_text(mesaj)

# 🌍 DÜNYA
async def dunya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone.utc)
    age = moon_age(now)

    mesaj = "🌍 GLOBAL RAPOR\n\n"

    def durum(a):
        if a < 1:
            return "❌"
        elif a < 2:
            return "⚠️"
        else:
            return "✅"

    mesaj += f"Türkiye: {durum(age-0.3)}\n"
    mesaj += f"Suudi: {durum(age)}\n"
    mesaj += f"İran: {durum(age-0.2)}\n"
    mesaj += f"Afganistan: {durum(age-0.4)}\n"
    mesaj += f"Afrika: {durum(age+0.5)}\n"
    mesaj += f"Amerika: {durum(age+1)}\n"

    await update.message.reply_text(mesaj)

# 🌍 KONUM (PRO)
async def konum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sehir = " ".join(context.args)

        cities = {
            "izmir": (38.42, 27.14),
            "istanbul": (41.01, 28.97),
            "mekke": (21.39, 39.86),
            "riyad": (24.71, 46.67),
            "tahran": (35.68, 51.41),
            "kabil": (34.55, 69.21),
        }

        if sehir.lower() not in cities:
            await update.message.reply_text("❌ Şehir yok\nÖrnek: /konum izmir")
            return

        lat, lon = cities[sehir.lower()]

        loc = LocationInfo(latitude=lat, longitude=lon)
        s = sun(loc.observer, date=datetime.utcnow())

        sunset = s["sunset"]

        obs = ephem.Observer()
        obs.lat = str(lat)
        obs.lon = str(lon)
        obs.date = sunset

        moon = ephem.Moon(obs)
        altitude = moon.alt * 180 / 3.1416

        mesaj = f"🌍 {sehir.upper()}\n\n"
        mesaj += f"Gün batımı: {sunset.strftime('%H:%M')}\n"
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
        await update.message.reply_text("Hata: /konum izmir")

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

# 🚀 MAIN
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
