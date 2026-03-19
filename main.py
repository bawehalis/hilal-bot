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
# 🌙 NEW MOON
# =========================
def get_new_moons(start=2024, end=2030):
    t0 = ts.utc(start, 1, 1)
    t1 = ts.utc(end, 12, 31)

    times, phases = find_discrete(t0, t1, moon_phases(eph))

    return [
        t.utc_datetime().replace(tzinfo=timezone.utc)
        for t, p in zip(times, phases)
        if p == 0
    ]

# =========================
# 🌙 HİLAL
# =========================
def hilal_visible(date):
    t = ts.utc(date.year, date.month, date.day, 18)

    e = earth.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    elong = m.separation_from(s).degrees

    loc = earth + Topos(21.4, 39.8)  # Mekke referans
    alt, _, _ = loc.at(t).observe(moon).apparent().altaz()

    return alt.degrees > 5 and elong > 10

# =========================
# 🔥 AY BAŞLANGIÇLARI
# =========================
def build_months():
    new_moons = get_new_moons()

    months = []

    for nm in new_moons:
        d1 = (nm + timedelta(days=1)).date()
        d2 = (nm + timedelta(days=2)).date()

        if hilal_visible(d1):
            months.append(d1)
        else:
            months.append(d2)

    return sorted(months)

# =========================
# 🔥 BUGÜN
# =========================
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()
    months = build_months()

    aylar = [
        "Muharrem","Safer","Rebiülevvel","Rebiülahir",
        "Cemaziyelevvel","Cemaziyelahir","Recep",
        "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
    ]

    # 🔥 DOĞRU ANCHOR (ZİLHİCCE 1)
    anchor_target = datetime(2025, 5, 28).date()

    anchor_index = min(
        range(len(months)),
        key=lambda i: abs((months[i] - anchor_target).days)
    )

    # 🔥 BUGÜNÜN AYI
    current_month = None
    current_index = 0

    for i, m in enumerate(months):
        if m <= today:
            current_month = m
            current_index = i

    if current_month is None:
        await update.message.reply_text("❌ Bulunamadı")
        return

    gun = (today - current_month).days + 1

    # 🔥 AY HESABI (FIX)
    ay_index = (current_index - anchor_index + 11) % 12

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

print("🚀 FINAL SİSTEM AKTİF")
app.run_polling()
