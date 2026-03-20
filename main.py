import os
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from skyfield.api import load, Topos
from skyfield.almanac import find_discrete, moon_phases

# =========================
# TOKEN
# =========================
TOKEN = os.getenv("TOKEN")
logging.basicConfig(level=logging.INFO)

# =========================
# SKYFIELD
# =========================
ts = load.timescale()
eph = load('de421.bsp')

earth = eph['earth']
moon = eph['moon']
sun = eph['sun']

# =========================
# LOCATIONS
# =========================
LOCATIONS = [
    Topos(21.4, 39.8),   # Mekke
    Topos(39.9, 32.8),   # Türkiye
    Topos(35.7, 51.4),   # İran
]

# =========================
# NEW MOON
# =========================
def get_new_moons(start=1995, end=2035):
    t0 = ts.utc(start, 1, 1)
    t1 = ts.utc(end, 12, 31)

    times, phases = find_discrete(t0, t1, moon_phases(eph))

    return [
        t.utc_datetime().replace(tzinfo=timezone.utc)
        for t, p in zip(times, phases)
        if p == 0
    ]

NEW_MOONS = get_new_moons()

# =========================
# HİLAL (SMART)
# =========================
def hilal_visible(date, nm):

    results = []

    for loc in LOCATIONS:

        visible_flag = False

        for hour in range(16, 23):

            t = ts.utc(date.year, date.month, date.day, hour)

            e = (earth + loc).at(t)
            m = e.observe(moon).apparent()
            s = e.observe(sun).apparent()

            alt, _, _ = m.altaz()
            elong = m.separation_from(s).degrees

            alt = alt.degrees

            age = (datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc) - nm).total_seconds()/3600

            # 🔥 ADAPTIVE MODEL (KRİTİK)
            if (
                (alt > 4 and elong > 8) or
                (alt > 3 and elong > 10) or
                (age > 16 and elong > 7)
            ):
                visible_flag = True
                break

        results.append(visible_flag)

    # çoğunluk kararı
    return sum(results) >= 2

# =========================
# AY BAŞI BUL
# =========================
def find_month_start(nm):

    nm_date = nm.date()

    day1 = nm_date + timedelta(days=1)
    day2 = nm_date + timedelta(days=2)

    # 🔥 ÖNCE +1 DENEME
    if hilal_visible(day1, nm):
        return day1

    # 🔥 AKILLI ERKEN DURUM
    age = (datetime.combine(day1, datetime.min.time(), tzinfo=timezone.utc) - nm).total_seconds()/3600

    if age > 20:
        return day1

    # 🔥 FALLBACK
    return day2

# =========================
# AY LİSTESİ
# =========================
def build_months():
    months = []

    for nm in NEW_MOONS:
        months.append(find_month_start(nm))

    return sorted(months)

MONTHS = build_months()

# =========================
# HİCRİ AYLAR
# =========================
AYLAR = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep",
    "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
]

# =========================
# ANCHOR (SABİT)
# =========================
ANCHOR_TARGET = datetime(2025, 5, 28).date()

ANCHOR_INDEX = min(
    range(len(MONTHS)),
    key=lambda i: abs((MONTHS[i] - ANCHOR_TARGET).days)
)

# =========================
# HİCRİ HESAP
# =========================
def get_hijri(date):

    current = None

    for i, m in enumerate(MONTHS):
        if m <= date:
            current = (m, i)

    if not current:
        return 0, "?"

    start, idx = current
    gun = (date - start).days + 1

    ay_index = (idx - ANCHOR_INDEX + 11) % 12

    return gun, AYLAR[ay_index]

# =========================
# KOMUTLAR
# =========================
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()
    g, a = get_hijri(today)

    await update.message.reply_text(
        f"📅 Bugün\n\nMiladi: {today}\nHicri: {g} {a}"
    )

async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    year = int(context.args[0])

    for i, m in enumerate(MONTHS):
        ay_index = (i - ANCHOR_INDEX + 11) % 12

        if m.year == year and ay_index == 8:
            await update.message.reply_text(
                f"🌙 Ramazan\nBaşlangıç: {m}\nBitiş: {m + timedelta(days=29)}"
            )
            return

async def arefe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    year = int(context.args[0])

    for i, m in enumerate(MONTHS):
        ay_index = (i - ANCHOR_INDEX + 11) % 12

        if m.year == year and ay_index == 11:
            await update.message.reply_text(
                f"🐑 Arefe: {m + timedelta(days=8)}\nBayram: {m + timedelta(days=9)}"
            )
            return

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 FINAL Hicri Motor\n\n"
        "/bugun\n"
        "/ramazan 2026\n"
        "/arefe 2026"
    )

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("ramazan", ramazan))
app.add_handler(CommandHandler("arefe", arefe))

print("🚀 FINAL SİSTEM AKTİF")
app.run_polling()
