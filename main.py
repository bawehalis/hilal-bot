import os
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from skyfield.api import load, Topos
import matplotlib.pyplot as plt

TOKEN = os.getenv("TOKEN")

logging.basicConfig(level=logging.INFO)

ts = load.timescale()
eph = load('de421.bsp')

earth = eph['earth']
moon = eph['moon']
sun = eph['sun']

COUNTRIES = {
    "Suudi Arabistan": (21.4, 39.8),
    "Türkiye": (39.0, 35.0),
    "İran": (35.0, 51.0),
    "Afganistan": (34.5, 69.2),
}

# 🌙 elongation
def elongation(t):
    e = earth.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()
    return m.separation_from(s).degrees

# 🌙 visibility
def visibility(lat, lon, date):
    t = ts.utc(date.year, date.month, date.day, 18)

    loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)
    alt, az, dist = loc.at(t).observe(moon).apparent().altaz()

    alt = alt.degrees
    el = elongation(t)

    if el < 7 or alt < 0:
        return 0
    elif alt < 5:
        return 1
    elif alt < 10:
        return 2
    else:
        return 3

# 🌙 ay başlangıcı
def find_month(date):
    for i in range(3):
        d = date + timedelta(days=i)

        for lat, lon in COUNTRIES.values():
            if visibility(lat, lon, d) == 3:
                return d

    return date + timedelta(days=1)

# 📅 yıl hesap
def calc_year(year):
    start = datetime(year,1,1,tzinfo=timezone.utc)
    months = []
    current = start

    for _ in range(12):
        m = find_month(current)
        months.append(m)
        current = m + timedelta(days=29)

    return months

# 🟢 BUGÜN
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()
    months = calc_year(today.year)

    hicri_ay = 1
    for i, m in enumerate(months):
        if today >= m.date():
            hicri_ay = i + 1

    baslangic = months[hicri_ay - 1].date()
    gun = (today - baslangic).days + 1

    msg = f"📅 BUGÜN\n\n"
    msg += f"Miladi: {today}\n"
    msg += f"Hicri Ay: {hicri_ay}\n"
    msg += f"Gün: {gun}\n\n"

    if hicri_ay == 9:
        msg += "🌙 Ramazan"
    elif hicri_ay == 10:
        msg += "🎉 Şevval (Bayram dönemi)"
    elif hicri_ay == 12:
        msg += "🕋 Zilhicce"
    else:
        msg += "Normal gün"

    await update.message.reply_text(msg)

# 🌍 HARİTA
def generate_map(date):
    lats,lons,colors = [],[],[]

    for lat in range(-60,61,5):
        for lon in range(-180,181,5):
            v = visibility(lat,lon,date)
            colors.append(["black","red","orange","green"][v])
            lats.append(lat)
            lons.append(lon)

    plt.figure(figsize=(12,6))
    plt.scatter(lons,lats,c=colors,s=10)

    file = "/tmp/map.png"
    plt.savefig(file)
    plt.close()

    return file

# 🚀 KOMUTLAR
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 FULL HİLAL BOT\n\n"
        "/bugun\n"
        "/hilal\n"
        "/ulke\n"
        "/harita\n"
        "/yil 2027"
    )

async def hilal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()
    v = visibility(21.4,39.8,today)

    durum = ["❌ Görünmez","⚠️ Çok zor","⚠️ Zor","✅ Görülebilir"][v]

    await update.message.reply_text(f"🌙 {durum}")

async def ulke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()
    msg = "🌍 ÜLKE\n\n"

    for name,(lat,lon) in COUNTRIES.items():
        v = visibility(lat,lon,today)
        msg += f"{name}: {['❌','⚠️','⚠️','✅'][v]}\n"

    await update.message.reply_text(msg)

async def harita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = generate_map(datetime.now(timezone.utc).date())
    await update.message.reply_photo(photo=open(file,"rb"))

async def yil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    year = int(context.args[0])
    months = calc_year(year)

    msg = f"{year}\n\n"
    for i,d in enumerate(months):
        msg += f"Ay {i+1}: {d.date()}\n"

    await update.message.reply_text(msg)

# 🚀 APP
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("hilal", hilal))
app.add_handler(CommandHandler("ulke", ulke))
app.add_handler(CommandHandler("harita", harita))
app.add_handler(CommandHandler("yil", yil))

print("Bot hazır 🚀")
app.run_polling()
