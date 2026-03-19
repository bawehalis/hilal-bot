import os
import logging
from datetime import datetime, timezone, timedelta

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from skyfield.api import load, Topos
from skyfield import almanac

TOKEN = os.getenv("TOKEN")

logging.basicConfig(level=logging.INFO)

ts = load.timescale()
eph = load('de421.bsp')

earth = eph['earth']
moon = eph['moon']
sun = eph['sun']

months = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep","Şaban",
    "Ramazan","Şevval","Zilkade","Zilhicce"
]

# 🌙 ELONGATION
def elongation(t):
    e = earth.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()
    return m.separation_from(s).degrees

# 🌇 SUNSET
def sunset(lat, lon, date):
    location = Topos(latitude_degrees=lat, longitude_degrees=lon)
    t0 = ts.utc(date.year, date.month, date.day)
    t1 = ts.utc(date.year, date.month, date.day + 1)

    f = almanac.sunrise_sunset(eph, location)
    times, events = almanac.find_discrete(t0, t1, f)

    for t, e in zip(times, events):
        if e == 0:
            return t
    return None

# 🌙 GÖRÜNÜRLÜK
def visible(lat, lon, date):
    t = sunset(lat, lon, date)
    if not t:
        return False

    loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)
    alt, _, _ = loc.at(t).observe(moon).apparent().altaz()

    el = elongation(t)

    return alt.degrees > 5 and el > 8

# 🌍 İLK GÖRÜLEN YER
def first_visibility(date):
    for lon in range(-20, 60, 5):
        for lat in range(-20, 40, 5):
            if visible(lat, lon, date):
                return (lat, lon)
    return None

# 📅 AY BAŞLANGICI BUL
def find_month_start(approx_date):
    for i in range(-2, 3):
        d = approx_date + timedelta(days=i)
        if first_visibility(d):
            return d
    return None

# 📅 YIL TAKVİMİ ÜRET
def generate_year(year):
    results = []

    # yaklaşık başlangıç (rastgele başlangıç noktası)
    current = datetime(year, 1, 1).date()

    # ilk ay başlangıcını bul
    start = find_month_start(current)

    for i in range(12):
        results.append(start)

        # sonraki ay yaklaşık 29.5 gün sonra
        approx = start + timedelta(days=29)
        start = find_month_start(approx)

    return results

# 🌍 ÜLKE SAATLERİ
def country_times(date):
    countries = {
        "Suudi": (21.39, 39.86, 3),
        "Türkiye": (39.0, 35.0, 3),
        "İran": (35.0, 51.0, 3.5),
        "Afganistan": (34.5, 69.2, 4.5),
    }

    out = ""

    for name, (lat, lon, tz) in countries.items():
        t = sunset(lat, lon, date)
        if not t:
            continue

        utc = t.utc_datetime().replace(tzinfo=timezone.utc)
        local = utc + timedelta(hours=tz)

        vis = visible(lat, lon, date)

        durum = "🌙 Görülebilir" if vis else "❌ Görünmez"

        out += f"{name}: {local.strftime('%H:%M')} → {durum}\n"

    return out

# 🚀 START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 Astronomik Hicri Takvim\n\n"
        "/yil 2027 → Tüm yıl\n"
        "/analiz → 3 günlük analiz"
    )

# 📅 YIL
async def yil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        year = int(context.args[0])
    except:
        await update.message.reply_text("Örnek: /yil 2027")
        return

    data = generate_year(year)

    mesaj = f"📅 {year} HİCRİ TAKVİM (ASTRONOMİK)\n\n"

    for i, d in enumerate(data):
        mesaj += f"{months[i]} → {d}\n"

    # Ramazan bul
    ramazan = data[8]
    mesaj += f"\n🌙 Ramazan başlangıç: {ramazan}\n"

    await update.message.reply_text(mesaj)

# 🔥 ANALİZ
async def analiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()

    mesaj = "🌍 3 GÜNLÜK HİLAL ANALİZİ\n\n"

    for i in [-1, 0, 1]:
        d = today + timedelta(days=i)

        vis = first_visibility(d)

        mesaj += f"{d}\n"

        if vis:
            mesaj += "🌍 İlk görülen bölge bulundu\n"
        else:
            mesaj += "❌ Görünmez\n"

        mesaj += country_times(d)
        mesaj += "\n"

    await update.message.reply_text(mesaj)

# 🚀 APP
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("yil", yil))
app.add_handler(CommandHandler("analiz", analiz))

print("TAKVİM MOTORU AKTİF 🚀")
app.run_polling()
