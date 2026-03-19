import os
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from skyfield.api import load, Topos
from skyfield.almanac import find_discrete, moon_phases

# =========================
TOKEN = os.getenv("TOKEN")
logging.basicConfig(level=logging.INFO)

# =========================
ts = load.timescale()
eph = load('de421.bsp')

earth = eph['earth']
moon = eph['moon']
sun = eph['sun']

# =========================
# 🌙 NEW MOON BUL
# =========================
def get_new_moons(year):
    t0 = ts.utc(year, 1, 1)
    t1 = ts.utc(year, 12, 31)

    times, phases = find_discrete(t0, t1, moon_phases(eph))

    new_moons = []
    for t, p in zip(times, phases):
        if p == 0:  # new moon
            new_moons.append(t.utc_datetime().replace(tzinfo=timezone.utc))

    return new_moons

# =========================
# 🌙 HİLAL GÖRÜLEBİLİR Mİ
# =========================
def hilal_visible(date):
    t = ts.utc(date.year, date.month, date.day, 18)

    e = earth.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    elong = m.separation_from(s).degrees

    loc = earth + Topos(21.4, 39.8)  # Mekke
    alt, _, _ = loc.at(t).observe(moon).apparent().altaz()

    return alt.degrees > 5 and elong > 10

# =========================
# 🔥 AY BAŞLANGIÇLARI
# =========================
def build_hijri_calendar(start=2025, end=2030):

    months = []

    for year in range(start, end+1):
        new_moons = get_new_moons(year)

        for nm in new_moons:

            next_day = nm + timedelta(days=1)

            if hilal_visible(next_day):
                start_day = next_day.date()
            else:
                start_day = (nm + timedelta(days=2)).date()

            months.append(start_day)

    months.sort()
    return months

# =========================
# 🔥 BUGÜN BUL
# =========================
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()

    months = build_hijri_calendar()

    aylar = [
        "Muharrem","Safer","Rebiülevvel","Rebiülahir",
        "Cemaziyelevvel","Cemaziyelahir","Recep",
        "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
    ]

    current_month = None
    ay_index = 0

    for i, m in enumerate(months):
        if m <= today:
            current_month = m
            ay_index = i

    if current_month is None:
        await update.message.reply_text("Bulunamadı")
        return

    gun = (today - current_month).days + 1
    ay = (ay_index % 12)

    await update.message.reply_text(
        f"📅 Bugün\n\nMiladi: {today}\nHicri: {gun} {aylar[ay]}"
    )

# =========================
# 🚀 START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 GERÇEK HİCRİ MOTOR\n\n/bugun"
    )

# =========================
# 🚀 APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))

print("🚀 CONJUNCTION MODEL AKTİF")
app.run_polling()
