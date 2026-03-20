import os
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from skyfield.api import load, Topos
from skyfield.almanac import find_discrete, moon_phases

TOKEN = os.getenv("TOKEN")
logging.basicConfig(level=logging.INFO)

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
# HİLAL MODELİ (NET)
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

    alt = alt.degrees

    if alt >= 4 and elong >= 5:
        return True

    if alt >= 6 and elong >= 4:
        return True

    if age >= 12 and elong >= 4:
        return True

    return False

# =========================
# 🔥 CHAIN MONTH GENERATION
# =========================
def build_calendar():

    months = []

    # ilk ay (anchor)
    current = datetime(2025,3,1).date()

    months.append(current)

    while current < datetime(2035,12,1).date():

        # sonraki new moon
        nm = min([x for x in NEW_MOONS if x.date() > current])

        next_start = None

        for i in range(1,4):
            d = (nm + timedelta(days=i)).date()

            if visible(d, nm):
                next_start = d
                break

        if not next_start:
            next_start = (nm + timedelta(days=2)).date()

        months.append(next_start)
        current = next_start

    return months

MONTHS = build_calendar()

# =========================
# HİCRİ
# =========================
AYLAR = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep",
    "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
]

ANCHOR_DATE = datetime(2025,3,1).date()
ANCHOR_INDEX = 0

# =========================
# HİCRİ BUL
# =========================
def get_hijri(date):

    idx = None

    for i,m in enumerate(MONTHS):
        if m <= date:
            idx = i

    if idx is None:
        return 0,"?"

    ay = (8 + idx) % 12

    start = MONTHS[idx]
    gun = (date - start).days + 1

    return gun, AYLAR[ay]

# =========================
# YIL ANALİZ
# =========================
def analyze_year(year):

    ramazan = None
    zilhicce = None

    for i,m in enumerate(MONTHS):

        ay = (8 + i) % 12

        if m.year == year:

            if ay == 8:
                ramazan = m

            if ay == 11:
                zilhicce = m

    return {
        "ramazan": ramazan,
        "bayram": ramazan + timedelta(days=29),
        "arefe": zilhicce + timedelta(days=8),
        "kurban": zilhicce + timedelta(days=9)
    }

# =========================
# BUGÜN
# =========================
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()
    g,a = get_hijri(today)

    await update.message.reply_text(
        f"📅 Bugün\n\nMiladi: {today}\nHicri: {g} {a}"
    )

# =========================
# TEST
# =========================
async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):

    REAL = {
        2020:"2020-04-24",
        2021:"2021-04-13",
        2022:"2022-04-02",
        2023:"2023-03-23",
        2024:"2024-03-11",
        2025:"2025-03-01"
    }

    text = "📊 TEST\n\n"
    total = 0

    for y, real_str in REAL.items():

        real = datetime.fromisoformat(real_str).date()
        model = analyze_year(y)["ramazan"]

        diff = (model - real).days
        total += abs(diff)

        text += f"{y}: {diff}\n"

    text += f"\nToplam hata: {total}"

    await update.message.reply_text(text)

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
"""🚀 GERÇEK HİCRİ MOTOR

/bugun
/test"""
    )

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("test", test))

print("🚀 CHAIN SYSTEM AKTİF")
app.run_polling()
