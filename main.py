import os
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from skyfield.api import load, Topos

TOKEN = os.getenv("TOKEN")

logging.basicConfig(level=logging.INFO)

ts = load.timescale()
eph = load('de421.bsp')

earth = eph['earth']
moon = eph['moon']
sun = eph['sun']

COUNTRIES = [
    (21.4,39.8),
    (39.0,35.0),
    (35.0,51.0),
    (34.5,69.2),
]

AREFE_DATA = {
    2020:"2020-07-30",
    2021:"2021-07-19",
    2022:"2022-07-08",
    2023:"2023-06-27",
    2024:"2024-06-15",
    2025:"2025-06-05",
}

# 🌙 elongation
def elongation(t):
    e = earth.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()
    return m.separation_from(s).degrees

# 🌙 görünürlük
def visible(date, lat, lon):
    t = ts.utc(date.year,date.month,date.day,18)

    loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)
    alt,_,_ = loc.at(t).observe(moon).apparent().altaz()

    return alt.degrees > 0 and elongation(t) > 7

# 🔥 model arefe
def model_arefe(year):
    start = datetime(year,1,1,tzinfo=timezone.utc)
    current = start
    months = []

    for _ in range(12):
        for i in range(3):
            d = current + timedelta(days=i)

            if any(visible(d,lat,lon) for lat,lon in COUNTRIES):
                months.append(d)
                current = d + timedelta(days=29)
                break

    return months[11] + timedelta(days=8)

# 🔥 OFFSET
def compute_offset():
    diffs = []

    for year, real_str in AREFE_DATA.items():
        real = datetime.fromisoformat(real_str)  # naive
        model = model_arefe(year).replace(tzinfo=None)  # FIX

        diff = (real - model).days
        diffs.append(diff)

    return round(sum(diffs)/len(diffs))

OFFSET = compute_offset()

# 🔥 kalibre arefe
def calibrated_arefe(year):
    return model_arefe(year) + timedelta(days=OFFSET)

# 🔥 yıl oluştur
def build_year(year):
    arefe = calibrated_arefe(year)

    months = [None]*12
    months[11] = arefe - timedelta(days=8)

    for i in range(10,-1,-1):
        months[i] = months[i+1] - timedelta(days=29)

    return months

# 🚀 BUGÜN
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()
    months = build_year(today.year)

    ay = 1
    for i,m in enumerate(months):
        if today >= m.date():
            ay = i+1

    gun = (today - months[ay-1].date()).days + 1

    ay_isimleri = [
        "Muharrem","Safer","Rebiülevvel","Rebiülahir",
        "Cemaziyelevvel","Cemaziyelahir","Recep",
        "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
    ]

    msg = f"📅 BUGÜN\n\n"
    msg += f"Miladi: {today}\n"
    msg += f"Hicri: {gun} {ay_isimleri[ay-1]}\n\n"
    msg += f"⚙️ Offset: {OFFSET} gün"

    await update.message.reply_text(msg)

# 🚀 START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 HİCRİ MOTOR\n\n"
        "/bugun"
    )

# 🚀 APP
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))

print("Çalışıyor 🚀")
app.run_polling()
