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

# 🌍 ÜLKELER
COUNTRIES = {
    "Suudi Arabistan": (21.4, 39.8, 3),
    "Türkiye": (39.0, 35.0, 3),
    "İran": (35.0, 51.0, 3.5),
    "Afganistan": (34.5, 69.2, 4.5),
}

# 🌙 elongation
def elongation(t):
    e = earth.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()
    return m.separation_from(s).degrees

# 🌙 görünürlük
def visibility(lat, lon, date):
    t = ts.utc(date.year, date.month, date.day, 18)

    loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)
    alt, az, dist = loc.at(t).observe(moon).apparent().altaz()

    alt = alt.degrees
    el = elongation(t)

    if el < 7 or alt < 0:
        return 0, alt, el
    elif alt < 5:
        return 1, alt, el
    elif alt < 10:
        return 2, alt, el
    else:
        return 3, alt, el

# 🌍 HARİTA
def generate_map(date):
    lats, lons, colors = [], [], []

    for lat in range(-60, 61, 5):
        for lon in range(-180, 181, 5):
            v, _, _ = visibility(lat, lon, date)

            lats.append(lat)
            lons.append(lon)

            colors.append(["black","red","orange","green"][v])

    plt.figure(figsize=(12,6))
    plt.scatter(lons, lats, c=colors, s=10)
    plt.title("Hilal Görünürlük Haritası")

    file = "/tmp/map.png"
    plt.savefig(file)
    plt.close()
    return file

# 🌙 AY BAŞLANGICI
def find_month(date):
    for i in range(3):
        d = date + timedelta(days=i)

        for lat, lon, _ in COUNTRIES.values():
            v, _, _ = visibility(lat, lon, d)
            if v == 3:
                return d

    return date + timedelta(days=1)

# 📅 YIL
def calc_year(year):
    start = datetime(year,1,1,tzinfo=timezone.utc)
    months = []
    current = start

    for _ in range(12):
        m = find_month(current)
        months.append(m)
        current = m + timedelta(days=29)

    return months

# 🚀 KOMUTLAR

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 FULL HİLAL ANALİZ SİSTEMİ\n\n"
        "/hilal\n"
        "/ulke\n"
        "/ulke_detay\n"
        "/harita\n"
        "/yil 2027\n"
        "/tahmin\n"
        "/analiz"
    )

async def hilal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = datetime.now(timezone.utc).date()
    v, alt, el = visibility(21.4,39.8,date)

    durum = ["❌ Görünmez","⚠️ Çok zor","⚠️ Zor","✅ Görülebilir"][v]

    await update.message.reply_text(
        f"🌙 Genel Durum\n\n"
        f"Durum: {durum}\n"
        f"Yükseklik: {alt:.2f}°\n"
        f"Elongation: {el:.2f}°"
    )

async def ulke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = datetime.now(timezone.utc).date()
    msg = "🌍 ÜLKE ANALİZİ\n\n"

    for name,(lat,lon,_) in COUNTRIES.items():
        v,_,_ = visibility(lat,lon,date)
        durum = ["❌","⚠️","⚠️","✅"][v]
        msg += f"{name}: {durum}\n"

    await update.message.reply_text(msg)

async def ulke_detay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = datetime.now(timezone.utc).date()
    msg = "🔬 DETAY ANALİZ\n\n"

    for name,(lat,lon,_) in COUNTRIES.items():
        v,alt,el = visibility(lat,lon,date)

        msg += f"{name}\n"
        msg += f"Alt: {alt:.2f}°\n"
        msg += f"Elong: {el:.2f}°\n\n"

    await update.message.reply_text(msg)

async def harita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = generate_map(datetime.now(timezone.utc).date())
    await update.message.reply_photo(photo=open(file,"rb"))

async def yil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    year = int(context.args[0])
    months = calc_year(year)

    msg = f"📅 {year}\n\n"

    for i,d in enumerate(months):
        msg += f"Ay {i+1}: {d.date()}\n"

    await update.message.reply_text(msg)

async def tahmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()

    tomorrow = today + timedelta(days=1)

    v_today,_,_ = visibility(21.4,39.8,today)
    v_tomorrow,_,_ = visibility(21.4,39.8,tomorrow)

    msg = "🔮 TAHMİN\n\n"

    if v_today == 0 and v_tomorrow > 0:
        msg += "➡️ Yarın hilal görülebilir"
    elif v_today > 0:
        msg += "➡️ Bugün zaten mümkün"
    else:
        msg += "➡️ Henüz mümkün değil"

    await update.message.reply_text(msg)

async def analiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    date = datetime.now(timezone.utc).date()

    v,alt,el = visibility(21.4,39.8,date)

    msg = "🧠 ANALİZ\n\n"

    if v == 0:
        msg += "Bugün hilal imkansız → erken ilan hatalı olur"
    elif v == 1:
        msg += "Çok zor → tartışmalı"
    elif v == 2:
        msg += "Zor → dikkatli olunmalı"
    else:
        msg += "Bilimsel olarak mümkün"

    await update.message.reply_text(msg)

# 🚀 APP
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("hilal", hilal))
app.add_handler(CommandHandler("ulke", ulke))
app.add_handler(CommandHandler("ulke_detay", ulke_detay))
app.add_handler(CommandHandler("harita", harita))
app.add_handler(CommandHandler("yil", yil))
app.add_handler(CommandHandler("tahmin", tahmin))
app.add_handler(CommandHandler("analiz", analiz))

print("FULL SİSTEM ÇALIŞIYOR 🚀")
app.run_polling()
