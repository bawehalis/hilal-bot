import os
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, JobQueue

from skyfield.api import load, Topos

TOKEN = os.getenv("TOKEN")

logging.basicConfig(level=logging.INFO)

ts = load.timescale()
eph = load('de421.bsp')

earth = eph['earth']
moon = eph['moon']
sun = eph['sun']

# 🌍 ÜLKELER
COUNTRIES = {
    "suudi": (21.4, 39.8),
    "turkiye": (39.0, 35.0),
    "iran": (35.0, 51.0),
    "afganistan": (34.5, 69.2),
}

# 🔥 AREFE DATA (kalibrasyon)
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
    t = ts.utc(date.year, date.month, date.day, 18)

    loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)
    alt,_,_ = loc.at(t).observe(moon).apparent().altaz()

    return alt.degrees > 0 and elongation(t) > 7

# 🔥 AY BAŞLANGICI (ülkeye göre)
def find_month(date, lat, lon):
    for i in range(3):
        d = date + timedelta(days=i)
        if visible(d, lat, lon):
            return d
    return date + timedelta(days=1)

# 🔥 YIL HESAP (ülkeye göre)
def build_year_country(year, lat, lon):
    start = datetime(year,1,1,tzinfo=timezone.utc)
    months = []
    current = start

    for _ in range(12):
        m = find_month(current, lat, lon)
        months.append(m)
        current = m + timedelta(days=29)

    return months

# 🔥 KALİBRASYON OFFSET
def compute_offset():
    diffs = []
    for y,d in AREFE_DATA.items():
        real = datetime.fromisoformat(d)
        model = build_year_country(y,21.4,39.8)[11] + timedelta(days=8)
        diffs.append((real-model).days)
    return round(sum(diffs)/len(diffs))

OFFSET = compute_offset()

# 🔥 KALİBRE EDİLMİŞ TAKVİM
def build_calibrated(year, lat, lon):
    months = build_year_country(year, lat, lon)
    return [m + timedelta(days=OFFSET) for m in months]

# 📅 BUGÜN (ülkeye göre)
def today_hijri(lat, lon):
    today = datetime.now(timezone.utc).date()
    months = build_calibrated(today.year, lat, lon)

    ay = 1
    for i,m in enumerate(months):
        if today >= m.date():
            ay = i+1

    gun = (today - months[ay-1].date()).days + 1
    return ay, gun

# 🚀 /ulke_takvim
async def ulke_takvim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ulke = context.args[0].lower()
    except:
        await update.message.reply_text("Örnek: /ulke_takvim turkiye")
        return

    if ulke not in COUNTRIES:
        await update.message.reply_text("❌ Ülke yok")
        return

    lat, lon = COUNTRIES[ulke]

    ay, gun = today_hijri(lat, lon)

    await update.message.reply_text(
        f"📍 {ulke.upper()}\n\n"
        f"Hicri Ay: {ay}\n"
        f"Gün: {gun}"
    )

# 🚀 /karsilastir_ulke
async def karsilastir_ulke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ay_t, gun_t = today_hijri(*COUNTRIES["turkiye"])
    ay_s, gun_s = today_hijri(*COUNTRIES["suudi"])

    await update.message.reply_text(
        "📊 TÜRKİYE vs SUUDİ\n\n"
        f"🇹🇷 Türkiye: {ay_t}.{gun_t}\n"
        f"🇸🇦 Suudi: {ay_s}.{gun_s}"
    )

# 🚀 RAMAZAN KONTROL (otomatik)
async def ramazan_kontrol(context: ContextTypes.DEFAULT_TYPE):
    bot = context.bot

    lat, lon = COUNTRIES["turkiye"]
    ay, gun = today_hijri(lat, lon)

    if ay == 9 and gun == 1:
        await bot.send_message(
            chat_id=context.job.chat_id,
            text="🌙 RAMAZAN BAŞLADI!"
        )

# 🚀 /ramazan_abone
async def ramazan_abone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    context.job_queue.run_daily(
        ramazan_kontrol,
        time=datetime.now().time(),
        chat_id=chat_id,
        name=str(chat_id)
    )

    await update.message.reply_text("🔔 Ramazan bildirimi aktif")

# 🚀 START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 GLOBAL HİCRİ MOTOR\n\n"
        "/ulke_takvim turkiye\n"
        "/karsilastir_ulke\n"
        "/ramazan_abone"
    )

# 🚀 APP
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ulke_takvim", ulke_takvim))
app.add_handler(CommandHandler("karsilastir_ulke", karsilastir_ulke))
app.add_handler(CommandHandler("ramazan_abone", ramazan_abone))

print("ULTRA SİSTEM AKTİF 🚀")
app.run_polling()
