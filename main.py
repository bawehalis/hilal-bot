import os
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from skyfield.api import load, Topos

# =========================
# TOKEN
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

LOCATIONS = [
    (21.4, 39.8),
    (39.0, 35.0),
    (35.0, 51.0),
    (34.5, 69.2),
]

# =========================
# HİLAL (OPTİMUM KRİTER)
# =========================
def hilal_var(date):
    t = ts.utc(date.year, date.month, date.day, 18)

    e = earth.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    elong = m.separation_from(s).degrees

    for lat, lon in LOCATIONS:
        loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)
        alt, _, _ = loc.at(t).observe(moon).apparent().altaz()

        # 🔥 DENGELİ KRİTER
        if alt.degrees > 4 and elong > 9:
            return True

    return False

# =========================
# 🔥 ANCHOR (KESİN DOĞRU)
# =========================
# 2025 Arefe = 5 Haziran
ANCHOR_DATE = datetime(2025, 6, 5, tzinfo=timezone.utc)
ANCHOR_DAY = 9
ANCHOR_MONTH = 12  # Zilhicce

# =========================
# 🔥 ANA MOTOR (HER GÜN HİLAL)
# =========================
def build_timeline():
    timeline = []

    current = ANCHOR_DATE
    gun = ANCHOR_DAY
    ay = ANCHOR_MONTH

    while current.year <= 2035:

        timeline.append((current, gun, ay))

        next_day = current + timedelta(days=1)

        # 🔥 HER GÜN HİLAL KONTROLÜ
        if hilal_var(next_day):
            gun = 1
            ay += 1
            if ay > 12:
                ay = 1
        else:
            gun += 1

        current = next_day

    return timeline

# =========================
# 📅 BUGÜN
# =========================
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()

    timeline = build_timeline()

    for d, gun, ay in timeline:
        if d.date() == today:

            aylar = [
                "Muharrem","Safer","Rebiülevvel","Rebiülahir",
                "Cemaziyelevvel","Cemaziyelahir","Recep",
                "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
            ]

            await update.message.reply_text(
                f"📅 Bugün\n\n"
                f"Miladi: {today}\n"
                f"Hicri: {gun} {aylar[ay-1]}"
            )
            return

    await update.message.reply_text("❌ Bulunamadı")

# =========================
# 📆 YIL
# =========================
async def yil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        year = int(context.args[0])
    except:
        await update.message.reply_text("Örnek: /yil 2026")
        return

    timeline = build_timeline()

    aylar = [
        "Muharrem","Safer","Rebiülevvel","Rebiülahir",
        "Cemaziyelevvel","Cemaziyelahir","Recep",
        "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
    ]

    months = {}

    for d, gun, ay in timeline:
        if d.year == year and gun == 1:
            months[ay] = d.date()

    text = f"📅 {year} Hicri Aylar\n\n"

    for i in range(1,13):
        if i in months:
            text += f"{aylar[i-1]}: {months[i]}\n"

    await update.message.reply_text(text)

# =========================
# 🚀 START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 Gerçek Hicri Motor\n\n"
        "/bugun\n"
        "/yil 2026"
    )

# =========================
# 🚀 APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("yil", yil))

print("🚀 GERÇEK SİSTEM AKTİF")
app.run_polling()
