import os
import logging
import numpy as np
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from skyfield.api import load, Topos
from skyfield.almanac import find_discrete, moon_phases

# =========================
# CONFIG
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
# ANCHOR
# =========================
ANCHOR_DATE = datetime(2026,3,20).date()  # 1 Şevval
ANCHOR_MONTH_INDEX = 9

# =========================
# LOCATIONS (multi-region)
# =========================
LOCATIONS = [
    Topos(21.4,39.8),   # Mekke
    Topos(39.9,32.8),   # Ankara
    Topos(35.7,51.4),   # Tahran
]

# =========================
# ML PARAMS
# =========================
PARAMS = {
    "ALT_MIN": 4,
    "ELONG_MIN": 5,
    "AGE_MIN": 12,
    "Q_THRESHOLD": 0
}

# =========================
# REAL DATA (expand later)
# =========================
REAL_STARTS = {
    datetime(2023,3,23).date(): "Ramazan",
    datetime(2024,3,11).date(): "Ramazan",
    datetime(2025,3,1).date(): "Ramazan",
}

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
# VISIBILITY (ML + YALLOP)
# =========================
def visible(date, nm):

    t = ts.utc(date.year, date.month, date.day, 18)
    results = []

    for loc in LOCATIONS:

        e = (earth + loc).at(t)
        m = e.observe(moon).apparent()
        s = e.observe(sun).apparent()

        alt, _, _ = m.altaz()
        elong = m.separation_from(s).degrees
        alt = alt.degrees

        age = (datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc) - nm).total_seconds()/3600

        W = max(alt / 10, 0)
        q = (elong - 11.8371 + 6.3226*W - 0.7319*(W**2) + 0.1018*(W**3)) / 10

        score = (
            (alt >= PARAMS["ALT_MIN"]) +
            (elong >= PARAMS["ELONG_MIN"]) +
            (age >= PARAMS["AGE_MIN"]) +
            (q >= PARAMS["Q_THRESHOLD"])
        )

        results.append(score)

    return sum(results)/len(results) >= 2.5

# =========================
# MONTH FINDING
# =========================
def find_next_month(current):

    nm = min([x for x in NEW_MOONS if x.date() > current])

    for i in range(1,4):
        d = (nm + timedelta(days=i)).date()

        if visible(d, nm):
            return d

    return (nm + timedelta(days=2)).date()

def find_prev_month(current):

    nm = max([x for x in NEW_MOONS if x.date() < current])

    for i in range(3,0,-1):
        d = (nm + timedelta(days=i)).date()

        if visible(d, nm):
            return d

    return (nm + timedelta(days=2)).date()

# =========================
# CALENDAR BUILD
# =========================
def build_calendar():

    months = {ANCHOR_DATE: ANCHOR_MONTH_INDEX}

    current = ANCHOR_DATE
    idx = ANCHOR_MONTH_INDEX

    # forward
    while current < datetime(2035,1,1).date():
        nxt = find_next_month(current)
        idx = (idx + 1) % 12
        months[nxt] = idx
        current = nxt

    # backward
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
# HIJRI
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
# ML LOSS
# =========================
def calculate_loss():

    error = 0

    for real_date in REAL_STARTS:
        pred = find_prev_month(real_date)
        diff = abs((pred - real_date).days)
        error += diff

    return error / len(REAL_STARTS)

# =========================
# TRAIN
# =========================
def train_model(iterations=50):

    global PARAMS

    best_params = PARAMS.copy()
    best_loss = calculate_loss()

    for _ in range(iterations):

        new_params = {
            "ALT_MIN": PARAMS["ALT_MIN"] + np.random.uniform(-1,1),
            "ELONG_MIN": PARAMS["ELONG_MIN"] + np.random.uniform(-1,1),
            "AGE_MIN": PARAMS["AGE_MIN"] + np.random.uniform(-3,3),
            "Q_THRESHOLD": PARAMS["Q_THRESHOLD"] + np.random.uniform(-0.2,0.2),
        }

        old = PARAMS.copy()
        PARAMS = new_params

        loss = calculate_loss()

        if loss < best_loss:
            best_loss = loss
            best_params = new_params
        else:
            PARAMS = old

    PARAMS = best_params
    return best_loss

# =========================
# COMMANDS
# =========================
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()
    g,a = get_hijri(today)

    await update.message.reply_text(
        f"📅 Bugün\n\nMiladi: {today}\nHicri: {g} {a}"
    )

async def train(update: Update, context: ContextTypes.DEFAULT_TYPE):

    loss = train_model()

    await update.message.reply_text(
        f"🤖 Eğitim tamamlandı\nLoss: {round(loss,2)}\nParams: {PARAMS}"
    )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
"""🚀 Hicri AI Motor

/bugun
/train"""
    )

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("train", train))

print("🚀 ML + HİLAL + CHAIN AKTİF")
app.run_polling()
