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
# ANCHOR (KESİN DOĞRU)
# =========================
ANCHOR_DATE = datetime(2026,3,20).date()  # 1 Şevval
ANCHOR_MONTH_INDEX = 9  # Şevval

# =========================
# NEW MOONS
# =========================
def get_new_moons():
    t0 = ts.utc(2000,1,1)
    t1 = ts.utc(2040,12,31)

    times, phases = find_discrete(t0, t1, moon_phases(eph))

    return [
        t.utc_datetime().replace(tzinfo=timezone.utc)
        for t,p in zip(times, phases)
        if p == 0
    ]

NEW_MOONS = get_new_moons()

# =========================
# HİLAL MODELİ
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

    # 🔥 STABLE MODEL
    if alt >= 4 and elong >= 5:
        return True

    if alt >= 6 and elong >= 4:
        return True

    if age >= 12 and elong >= 4:
        return True

    return False

# =========================
# AY BUL (TEK)
# =========================
def find_next_month(current):

    nm = min([x for x in NEW_MOONS if x.date() > current])

    for i in range(1,4):
        d = (nm + timedelta(days=i)).date()

        if visible(d, nm):
            # erkense kaydır
            if (d - nm.date()).days == 1:
                return d + timedelta(days=1)
            return d

    return (nm + timedelta(days=2)).date()

def find_prev_month(current):

    nm = max([x for x in NEW_MOONS if x.date() < current])

    for i in range(3,0,-1):
        d = (nm + timedelta(days=i)).date()

        if visible(d, nm):
            if (d - nm.date()).days == 1:
                return d + timedelta(days=1)
            return d

    return (nm + timedelta(days=2)).date()

# =========================
# 🔥 CHAIN TAKVİM
# =========================
def build_calendar():

    months = {ANCHOR_DATE: ANCHOR_MONTH_INDEX}

    # ileri
    current = ANCHOR_DATE
    idx = ANCHOR_MONTH_INDEX

    while current < datetime(2035,1,1).date():

        nxt = find_next_month(current)
        idx = (idx + 1) % 12

        months[nxt] = idx
        current = nxt

    # geri
    current = ANCHOR_DATE
    idx = ANCHOR_MONTH_INDEX

    while current > datetime(2000,1,1).date():

        prev = find_prev_month(current)
        idx = (idx - 1) % 12

        months[prev] = idx
        current = prev

    return sorted(months.items())

CALENDAR = build_calendar()

# =========================
# HİCRİ
# =========================
AYLAR = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep",
    "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
]

def get_hijri(date):

    current = None

    for d, idx in CALENDAR:
        if d <= date:
            current = (d, idx)

    if not current:
        return 0,"?"

    start, idx = current
    gun = (date - start).days + 1

    return gun, AYLAR[idx]

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
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
"""🚀 Hicri Motor (ANCHOR SYSTEM)

/bugun"""
    )

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))

print("🚀 ANCHOR + CHAIN AKTİF")
app.run_polling()
