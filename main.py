import os
import logging
from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

TOKEN = os.getenv("TOKEN")
logging.basicConfig(level=logging.INFO)

# =========================
# DATASET (SEN DOLDURACAKSIN)
# =========================
AREFE_DATA = {
    # örnek:
    # 2025: "2025-06-05",
}

# =========================
# AREFE ANALİZ
# =========================
async def analiz(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if len(AREFE_DATA) < 5:
        await update.message.reply_text("❌ En az 5 veri gir")
        return

    dates = []

    for y, d in AREFE_DATA.items():
        dt = datetime.fromisoformat(d)
        dates.append(dt)

    # farkları hesapla
    diffs = []

    for i in range(1, len(dates)):
        diff = (dates[i] - dates[i-1]).days
        diffs.append(diff)

    avg = sum(diffs) / len(diffs)

    text = "📊 AREFE ANALİZ\n\n"

    for i, d in enumerate(diffs):
        text += f"Yıl {i}: {d} gün\n"

    text += f"\n📉 Ortalama yıl kayması: {round(avg,2)} gün"

    # hicri yıl ~354 gün
    text += "\n\n🧠 MODEL\n"
    text += f"Hicri yıl: ~354 gün\n"
    text += f"Senin veri: {round(avg,2)}\n"

    if avg > 354:
        text += "\n📉 Sistem gecikmeli"
    else:
        text += "\n📈 Sistem erken"

    await update.message.reply_text(text)

# =========================
# VERİ EKLE
# =========================
async def ekle(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        y = int(context.args[0])
        d = context.args[1]

        AREFE_DATA[y] = d

        await update.message.reply_text(f"✅ Eklendi: {y} → {d}")

    except:
        await update.message.reply_text("❌ Format: /ekle 2025 2025-06-05")

# =========================
# LİSTE
# =========================
async def liste(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = "📅 DATASET\n\n"

    for y,d in sorted(AREFE_DATA.items()):
        text += f"{y}: {d}\n"

    await update.message.reply_text(text)

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
"""🧠 AREFE TRAIN BOT

/ekle 2025 2025-06-05
/liste
/analiz"""
    )

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ekle", ekle))
app.add_handler(CommandHandler("liste", liste))
app.add_handler(CommandHandler("analiz", analiz))

print("🚀 AREFE TRAIN BOT AKTİF")
app.run_polling()
