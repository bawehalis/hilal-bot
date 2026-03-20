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

LOCATIONS = [
    Topos(21.4, 39.8),
    Topos(39.9, 32.8),
    Topos(35.7, 51.4),
]

# =========================
# NEW MOON
# =========================
def get_new_moons(start=1995, end=2035):
    t0 = ts.utc(start,1,1)
    t1 = ts.utc(end,12,31)

    times, phases = find_discrete(t0, t1, moon_phases(eph))

    return [
        t.utc_datetime().replace(tzinfo=timezone.utc)
        for t,p in zip(times, phases)
        if p == 0
    ]

NEW_MOONS = get_new_moons()

# =========================
# SCORE
# =========================
def hilal_score(date, nm):

    total = 0
    count = 0

    for loc in LOCATIONS:
        for hour in range(16,23):

            t = ts.utc(date.year, date.month, date.day, hour)

            e = (earth + loc).at(t)
            m = e.observe(moon).apparent()
            s = e.observe(sun).apparent()

            alt, _, _ = m.altaz()
            elong = m.separation_from(s).degrees

            alt = alt.degrees

            age = (datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc) - nm).total_seconds()/3600

            score = (
                alt * 1.2 +
                elong * 0.9 +
                age * 0.04
            )

            total += score
            count += 1

    return total / count

# =========================
# AY BAŞI (KARAR)
# =========================
def find_month_start(nm):

    d1 = nm.date() + timedelta(days=1)
    d2 = nm.date() + timedelta(days=2)

    s1 = hilal_score(d1, nm)
    s2 = hilal_score(d2, nm)

    # 🔥 kritik fark
    if s1 > 15:
        return d1

    if s2 - s1 > 1.5:
        return d2

    return d1

# =========================
# MONTHS
# =========================
def build_months():
    return sorted([find_month_start(nm) for nm in NEW_MOONS])

MONTHS = build_months()

AYLAR = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep",
    "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
]

ANCHOR_TARGET = datetime(2025,5,28).date()

ANCHOR_INDEX = min(
    range(len(MONTHS)),
    key=lambda i: abs((MONTHS[i] - ANCHOR_TARGET).days)
)

# =========================
# HİCRİ
# =========================
def get_hijri(date):

    current = None

    for i,m in enumerate(MONTHS):
        if m <= date:
            current = (m,i)

    if not current:
        return 0,"?"

    start, idx = current
    gun = (date - start).days + 1

    ay_index = (idx - ANCHOR_INDEX + 11) % 12

    return gun, AYLAR[ay_index]

# =========================
# REAL DATA
# =========================
REAL_RAMADAN = {
    1995: datetime(1995,2,1).date(),
    1996: datetime(1996,1,22).date(),
    1997: datetime(1997,1,11).date(),
    1998: datetime(1998,12,20).date(),
    1999: datetime(1999,12,9).date(),
    2000: datetime(2000,11,27).date(),
    2001: datetime(2001,11,16).date(),
    2002: datetime(2002,11,6).date(),
    2003: datetime(2003,10,27).date(),
    2004: datetime(2004,10,15).date(),
    2005: datetime(2005,10,4).date(),
    2006: datetime(2006,9,24).date(),
    2007: datetime(2007,9,13).date(),
    2008: datetime(2008,9,1).date(),
    2009: datetime(2009,8,22).date(),
    2010: datetime(2010,8,11).date(),
    2011: datetime(2011,8,1).date(),
    2012: datetime(2012,7,20).date(),
    2013: datetime(2013,7,9).date(),
    2014: datetime(2014,6,28).date(),
    2015: datetime(2015,6,18).date(),
    2016: datetime(2016,6,6).date(),
    2017: datetime(2017,5,27).date(),
    2018: datetime(2018,5,16).date(),
    2019: datetime(2019,5,6).date(),
    2020: datetime(2020,4,24).date(),
    2021: datetime(2021,4,13).date(),
    2022: datetime(2022,4,2).date(),
    2023: datetime(2023,3,23).date(),
    2024: datetime(2024,3,11).date(),
    2025: datetime(2025,3,1).date(),
}

# =========================
# ANALİZ
# =========================
async def analiz(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = "📊 ANALİZ\n\n"

    correct = 0
    total = 0

    for year in REAL_RAMADAN:

        real = REAL_RAMADAN[year]
        pred = None

        for i,m in enumerate(MONTHS):
            idx = (i - ANCHOR_INDEX + 11) % 12
            if m.year == year and idx == 8:
                pred = m
                break

        if pred:
            diff = (pred - real).days
            text += f"{year}: {pred} ({diff})\n"

            if abs(diff) <= 1:
                correct += 1

            total += 1

    acc = (correct/total)*100 if total else 0
    text += f"\nDoğruluk: %{round(acc,2)}"

    await update.message.reply_text(text)

# =========================
# BUGÜN
# =========================
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()
    g,a = get_hijri(today)

    await update.message.reply_text(
        f"📅 Bugün\nMiladi: {today}\nHicri: {g} {a}"
    )

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("/bugun\n/analiz")

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("analiz", analiz))

print("🚀 FINAL STABLE MODEL AKTİF")
app.run_polling()
