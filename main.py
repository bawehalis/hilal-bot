import os
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from skyfield.api import load, Topos
from skyfield.almanac import find_discrete, moon_phases

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
# NEW MOONS
# =========================
def get_new_moons():
    t0 = ts.utc(2000,1,1)
    t1 = ts.utc(2035,12,31)

    times, phases = find_discrete(t0, t1, moon_phases(eph))

    return [
        t.utc_datetime().replace(tzinfo=timezone.utc)
        for t,p in zip(times, phases)
        if p == 0
    ]

NEW_MOONS = get_new_moons()

# =========================
# HİLAL
# =========================
def visible(date, nm):

    t = ts.utc(date.year, date.month, date.day, 18)

    loc = earth + Topos(21.4,39.8)

    e = loc.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    alt, _, _ = m.altaz()
    elong = m.separation_from(s).degrees

    age = (datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc) - nm).total_seconds()/3600

    return alt.degrees > 5 and elong > 8 and age > 12

# =========================
# AY BAŞLANGIÇ
# =========================
def get_months():

    months = []

    for nm in NEW_MOONS:

        for i in [1,2,3]:
            d = (nm + timedelta(days=i)).date()

            if visible(d, nm):
                months.append(d)
                break
        else:
            months.append((nm + timedelta(days=2)).date())

    return sorted(months)

MONTHS = get_months()

# =========================
# ANCHOR
# =========================
ANCHOR_DATE = datetime(2025,3,1).date()

ANCHOR_INDEX = min(range(len(MONTHS)),
                   key=lambda i: abs((MONTHS[i]-ANCHOR_DATE).days))

AYLAR = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep",
    "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
]

# =========================
# HİCRİ
# =========================
def get_hijri(date):

    idx = None

    for i,m in enumerate(MONTHS):
        if m <= date:
            idx = i

    diff = idx - ANCHOR_INDEX
    ay = (8 + diff) % 12

    start = MONTHS[idx]
    gun = (date - start).days + 1

    return gun, AYLAR[ay]

# =========================
# TEST DATA
# =========================
REAL = {
    2020:"2020-04-24",
    2021:"2021-04-13",
    2022:"2022-04-02",
    2023:"2023-03-23",
    2024:"2024-03-11",
    2025:"2025-03-01",
}

# =========================
# TEST
# =========================
async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = "📊 TEST\n\n"
    total = 0

    for y, real_str in REAL.items():

        real = datetime.fromisoformat(real_str).date()

        model = None

        for i,m in enumerate(MONTHS):
            diff = i - ANCHOR_INDEX
            ay = (8 + diff) % 12

            if ay == 8 and m.year == y:
                model = m

        diff = (model - real).days
        total += abs(diff)

        text += f"{y}: {diff}\n"

    text += f"\nToplam hata: {total}"

    await update.message.reply_text(text)

# =========================
# COMMANDS
# =========================
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()
    g,a = get_hijri(today)
    await update.message.reply_text(f"{today}\nHicri: {g} {a}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 AKTİF\n/bugun\n/test")

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("test", test))

print("🚀 TAM SİSTEM AKTİF")
app.run_polling()
