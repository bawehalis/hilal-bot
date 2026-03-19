import os
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TOKEN")

# 🌙 Hicri dönüşüm (astronomik approx)
def gregorian_to_hijri(date):
    # Basit ama doğruya yakın algoritma
    jd = (date - datetime(622, 7, 16)).days
    hijri_year = int(jd / 354.367)
    remaining_days = jd - (hijri_year * 354.367)
    hijri_month = int(remaining_days / 29.5) + 1
    hijri_day = int(remaining_days % 29.5) + 1
    return hijri_year + 1, hijri_month, hijri_day

months = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep","Şaban",
    "Ramazan","Şevval","Zilkade","Zilhicce"
]

# 📌 /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Hilal Takvim Bot\n\n"
        "/bugun → Bugün ne?\n"
        "/yil 2026 → Hicri yıl\n"
        "/arefe → Arefe mi?\n"
        "/ramazan → Ramazan durumu"
    )

# 📅 /bugun
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.utcnow()
    hy, hm, hd = gregorian_to_hijri(now)

    mesaj = f"📅 Bugün:\n\n"
    mesaj += f"Miladi: {now.date()}\n"
    mesaj += f"Hicri: {hd} {months[hm-1]} {hy}\n\n"

    if hm == 12 and hd == 9:
        mesaj += "🌙 Bugün AREFE!"
    elif hm == 9:
        mesaj += "🌙 Ramazan ayındasın"
    else:
        mesaj += "Normal gün"

    await update.message.reply_text(mesaj)

# 📆 /yil
async def yil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        yil = int(context.args[0])
    except:
        await update.message.reply_text("Kullanım: /yil 2026")
        return

    mesaj = f"📆 {yil} Hicri Yaklaşık:\n\n"
    for i, ay in enumerate(months):
        mesaj += f"{i+1}. Ay → {ay}\n"

    await update.message.reply_text(mesaj)

# 🕋 /arefe
async def arefe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.utcnow()
    hy, hm, hd = gregorian_to_hijri(now)

    if hm == 12 and hd == 9:
        await update.message.reply_text("✅ Bugün Arefe")
    else:
        await update.message.reply_text("❌ Bugün arefe değil")

# 🌙 /ramazan
async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.utcnow()
    hy, hm, hd = gregorian_to_hijri(now)

    if hm == 9:
        await update.message.reply_text("🌙 Ramazan ayındasın")
    else:
        await update.message.reply_text("Ramazan değil")

# 🚀 MAIN
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("yil", yil))
app.add_handler(CommandHandler("arefe", arefe))
app.add_handler(CommandHandler("ramazan", ramazan))

print("Bot çalışıyor...")
app.run_polling()
