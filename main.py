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
    (21.4, 39.8),   # Mekke
    (39.0, 35.0),   # Türkiye
    (35.0, 51.0),   # İran
    (34.5, 69.2),   # Afganistan
]

# =========================
# HİLAL (GERÇEKÇİ KRİTER)
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

        if alt.degrees > 6 and elong > 11:
            return True

    return False

# =========================
# 🔥 ANCHOR (SON DOĞRU NOKTA)
# =========================
# 2025 Arefe (9 Zilhicce)
ANCHOR_DATE = datetime(2025, 6, 5, tzinfo=timezone.utc)
ANCHOR_DAY = 9
ANCHOR_MONTH = 12  # Zilhicce

# =========================
# 🔥 ANA MOTOR (İLERİ SİMÜLASYON)
# =========================
def build_timeline():
    timeline = []

    current = ANCHOR_DATE
    gun = ANCHOR_DAY
    ay = ANCHOR_MONTH

    # 2035'e kadar hesapla
    while current.year <= 2035:

        timeline.append((current, gun, ay))

        next_day = current + timedelta(days=1)

        gun += 1

        # ay sonu kontrol
        if gun > 30:
            if hilal_var(next_day):
                gun = 1
                ay += 1
                if ay > 12:
                    ay = 1

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

    await update.message.reply_text("❌ Bugün bulunamadı")

# =========================
# 📆 YIL ANALİZ
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
        "🌙 Hicri Motor (Anchor Model)\n\n"
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

print("🚀 ANCHOR SİSTEM AKTİF")
app.run_polling()
