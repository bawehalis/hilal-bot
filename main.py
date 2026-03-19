import os
import logging
import re
from datetime import datetime, timezone, timedelta

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters
)

from skyfield.api import load, Topos
from skyfield import almanac

TOKEN = os.getenv("TOKEN")

logging.basicConfig(level=logging.INFO)

ts = load.timescale()
eph = load('de421.bsp')

earth = eph['earth']
moon = eph['moon']

months = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep","Şaban",
    "Ramazan","Şevval","Zilkade","Zilhicce"
]

# 🌇 SUNSET
def get_sunset(lat, lon, date):
    try:
        location = Topos(latitude_degrees=lat, longitude_degrees=lon)

        t0 = ts.utc(date.year, date.month, date.day)
        t1 = ts.utc(date.year, date.month, date.day + 1)

        f = almanac.sunrise_sunset(eph, location)
        times, events = almanac.find_discrete(t0, t1, f)

        for t, e in zip(times, events):
            if e == 0:
                return t

        return None
    except:
        return None

# 🌙 HİLAL
def visible(lat, lon, date):
    t = get_sunset(lat, lon, date)

    if t is None:
        return False

    try:
        loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)
        alt, _, _ = loc.at(t).observe(moon).apparent().altaz()

        return alt.degrees > 5
    except:
        return False

# 🌍 İLK GÖRÜLEN
def first_visibility(date):
    for lon in range(-20, 60, 5):
        for lat in range(-20, 40, 5):
            if visible(lat, lon, date):
                return True
    return False

# 📅 AY BAŞLANGICI
def find_month_start(base_date):
    for i in range(-2, 3):
        d = base_date + timedelta(days=i)
        if first_visibility(d):
            return d
    return base_date

# 📅 YIL TAKVİMİ
def generate_year(year):
    results = []
    current = datetime(year, 1, 1).date()
    start = find_month_start(current)

    for _ in range(12):
        results.append(start)
        start = find_month_start(start + timedelta(days=29))

    return results

# 📅 TAKVİM
async def send_year(update, year):
    data = generate_year(year)

    msg = f"📅 {year} Hicri Takvim\n\n"

    for i, d in enumerate(data):
        msg += f"{months[i]} → {d}\n"

    msg += f"\n🌙 Ramazan: {data[8]}"

    await update.message.reply_text(msg)

# 🌍 ANALİZ
async def send_analysis(update):
    today = datetime.now(timezone.utc).date()

    msg = "🌍 3 GÜNLÜK HİLAL ANALİZİ\n\n"

    for i in [-1, 0, 1]:
        d = today + timedelta(days=i)

        if first_visibility(d):
            msg += f"{d} → 🌙 Görülebilir\n"
        else:
            msg += f"{d} → ❌ Görünmez\n"

    await update.message.reply_text(msg)

# 🚀 START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 Sistem aktif\n\n"
        "👉 2027 yaz\n"
        "👉 analiz yaz"
    )

# 🤖 SMART
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    print("GELEN:", text)

    if "analiz" in text:
        await send_analysis(update)
        return

    match = re.search(r'\d{4}', text)
    if match:
        year = int(match.group())
        if 1900 < year < 2100:
            await send_year(update, year)
            return

    await update.message.reply_text("❗ 2027 veya analiz yaz")

# 🚀 APP
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT, handle_message))

print("BOT AKTİF 🚀")
app.run_polling()
