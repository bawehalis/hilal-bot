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
def get_new_moons(start=2024, end=2030):
    t0 = ts.utc(start, 1, 1)
    t1 = ts.utc(end, 12, 31)

    times, phases = find_discrete(t0, t1, moon_phases(eph))

    new_moons = []
    for t, p in zip(times, phases):
        if p == 0:
            new_moons.append(
                t.utc_datetime().replace(tzinfo=timezone.utc)
            )

    return new_moons

# =========================
# 🌙 HİLAL GÖRÜNÜRLÜK
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
def build_hijri_months():
    new_moons = get_new_moons()

    months = []

    for nm in new_moons:

        day1 = (nm + timedelta(days=1)).date()
        day2 = (nm + timedelta(days=2)).date()

        if hilal_visible(day1):
            months.append(day1)
        else:
            months.append(day2)

    months.sort()
    return months

# =========================
# 🔥 BUGÜN
# =========================
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()

    months = build_hijri_months()

    aylar = [
        "Muharrem","Safer","Rebiülevvel","Rebiülahir",
        "Cemaziyelevvel","Cemaziyelahir","Recep",
        "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
    ]

    # 🔥 ANCHOR
    anchor_date = datetime(2025, 6, 5).date()
    anchor_index = None

    for i, m in enumerate(months):
        if abs((m - anchor_date).days) <= 2:
            anchor_index = i
            break

    if anchor_index is None:
        await update.message.reply_text("Anchor bulunamadı")
        return

    current_month = None
    current_index = 0

    for i, m in enumerate(months):
        if m <= today:
            current_month = m
            current_index = i

    if current_month is None:
        await update.message.reply_text("Bulunamadı")
        return

    gun = (today - current_month).days + 1

    ay_index = (current_index - anchor_index + 12) % 12

    await update.message.reply_text(
        f"📅 Bugün\n\nMiladi: {today}\nHicri: {gun} {aylar[ay_index]}"
    )

# =========================
# 🚀 START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 Hicri Motor FINAL\n\n/bugun"
    )

# =========================
# 🚀 APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))

print("🚀 SİSTEM AKTİF")
app.run_polling()
