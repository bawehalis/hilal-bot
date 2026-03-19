import os
from datetime import datetime, timezone
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import math

TOKEN = os.getenv("TOKEN")

# 🌙 Ay yaşı hesap (NASA approx)
def moon_age(date):
    diff = date - datetime(2001, 1, 1, tzinfo=timezone.utc)
    days = diff.total_seconds() / 86400
    lunations = 0.20439731 + (days * 0.03386319269)
    return (lunations % 1) * 29.53

# 🌙 Hicri dönüşüm (daha iyi approx)
def gregorian_to_hijri(date):
    jd = int((date - datetime(622, 7, 16, tzinfo=timezone.utc)).days)
    h_year = int((30 * jd + 10646) / 10631)
    h_month = min(12, math.ceil((jd - 29 - hijri_to_jd(h_year, 1, 1)) / 29.5) + 1)
    h_day = jd - hijri_to_jd(h_year, h_month, 1) + 1
    return h_year, h_month, h_day

def hijri_to_jd(year, month, day):
    return int((year - 1) * 354 + (3 + (11 * year)) / 30 + 29.5 * (month - 1) + day)

months = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep","Şaban",
    "Ramazan","Şevval","Zilkade","Zilhicce"
]

# 🚀 START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 Hilal Takvim Bot PRO\n\n"
        "/bugun → Bugün durumu\n"
        "/hilal → Hilal görünür mü?\n"
        "/arefe → Arefe mi?\n"
        "/ramazan → Ramazan durumu"
    )

# 📅 BUGÜN
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone.utc)
    hy, hm, hd = gregorian_to_hijri(now)

    mesaj = f"📅 Bugün:\n\n"
    mesaj += f"Miladi: {now.date()}\n"
    mesaj += f"Hicri: {hd} {months[hm-1]} {hy}\n\n"

    if hm == 12 and hd == 9:
        mesaj += "🕋 AREFE GÜNÜ"
    elif hm == 9:
        mesaj += "🌙 Ramazan"
    else:
        mesaj += "Normal gün"

    await update.message.reply_text(mesaj)

# 🌙 HİLAL
async def hilal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone.utc)
    age = moon_age(now)

    mesaj = f"🌙 Ay yaşı: {age:.2f} gün\n\n"

    if age < 1:
        mesaj += "❌ Hilal görünmez"
    elif 1 <= age < 2:
        mesaj += "⚠️ Zor görülebilir"
    else:
        mesaj += "✅ Hilal büyük ihtimalle görülebilir"

    await update.message.reply_text(mesaj)

# 🕋 AREFE
async def arefe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone.utc)
    hy, hm, hd = gregorian_to_hijri(now)

    if hm == 12 and hd == 9:
        await update.message.reply_text("✅ Bugün Arefe")
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
app.add_handler(CommandHandler("arefe", arefe))
app.add_handler(CommandHandler("ramazan", ramazan))

print("Bot çalışıyor...")
app.run_polling()
