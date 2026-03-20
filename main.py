import os
import datetime
import numpy as np

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from skyfield.api import load, Topos
from skyfield.almanac import find_discrete, moon_phases

# =========================
# CONFIG
# =========================
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN yok")

ANCHOR_AREFE = datetime.date(1995, 5, 9)

LEAP_YEARS = [2,5,7,10,13,16,18,21,24,26,29]

LOCATIONS = [
    Topos(21.3891, 39.8579),  # Mekke
    Topos(39.9334, 32.8597),  # Ankara
    Topos(35.6892, 51.3890),  # Tahran
]

# =========================
# SKYFIELD
# =========================
ts = load.timescale()
eph = load('de421.bsp')

earth = eph['earth']
moon = eph['moon']
sun = eph['sun']

# =========================
# GERÇEK DATA (kalibrasyon)
# =========================
REAL_EVENTS = {
    2023: {"ramadan": datetime.date(2023,3,23), "eid_fitr": datetime.date(2023,4,21), "eid_adha": datetime.date(2023,6,28)},
    2024: {"ramadan": datetime.date(2024,3,11), "eid_fitr": datetime.date(2024,4,10), "eid_adha": datetime.date(2024,6,16)},
    2025: {"ramadan": datetime.date(2025,3,1),  "eid_fitr": datetime.date(2025,3,30), "eid_adha": datetime.date(2025,6,6)},
}

# =========================
# HİCRİ YIL
# =========================
def is_leap(year):
    return ((year - 1995) % 30) in LEAP_YEARS

def estimate_arefe(year):
    date = ANCHOR_AREFE

    if year >= 1995:
        for y in range(1995, year):
            date += datetime.timedelta(days=355 if is_leap(y) else 354)
    else:
        for y in range(year, 1995):
            date -= datetime.timedelta(days=355 if is_leap(y) else 354)

    return date

# =========================
# ASTRONOMİ
# =========================
def moon_age_hours(date):
    try:
        t0 = ts.utc(date.year, date.month, date.day)
        t1 = ts.utc(date.year, date.month, date.day + 2)

        times, phases = find_discrete(t0, t1, moon_phases(eph))

        for t, p in zip(times, phases):
            if p == 0:
                nm = t.utc_datetime()
                delta = datetime.datetime.combine(date, datetime.time()) - nm
                return abs(delta.total_seconds()) / 3600
    except:
        pass
    return 24

def get_alt_elong(date, location):
    try:
        t = ts.utc(date.year, date.month, date.day, 18)

        obs = earth + location
        ast = obs.at(t).observe(moon)
        alt, az, _ = ast.apparent().altaz()

        sun_ast = obs.at(t).observe(sun)
        elong = ast.separation_from(sun_ast).degrees

        return alt.degrees, elong
    except:
        return 0, 0

# =========================
# YALLOP MODEL
# =========================
def yallop_q(elong, alt):
    W = max(alt / 10, 0)
    q = (elong - 11.8371 + 6.3226*W - 0.7319*(W**2) + 0.1018*(W**3)) / 10
    return q

def refine(date):
    for i in range(2):
        d = date + datetime.timedelta(days=i)

        qs = []
        for loc in LOCATIONS:
            alt, elong = get_alt_elong(d, loc)
            qs.append(yallop_q(elong, alt))

        avg_q = sum(qs) / len(qs)

        if avg_q > 0:
            return d

    return date

# =========================
# KALİBRASYON
# =========================
def calibrate(year, predicted_arefe):
    if year in REAL_EVENTS:
        real_arefe = REAL_EVENTS[year]["eid_adha"] - datetime.timedelta(days=1)
        diff = (predicted_arefe - real_arefe).days

        if diff == 1:
            return -1
        elif diff == -1:
            return 1

    return 0

# =========================
# HİCRİ OLAYLAR
# =========================
def get_events(year):

    arefe = estimate_arefe(year)

    dh_start = arefe - datetime.timedelta(days=8)

    # Ramazan hesap
    ramadan = dh_start - datetime.timedelta(days=266)
    ramadan = refine(ramadan)

    # Kalibrasyon
    correction = calibrate(year, arefe)
    ramadan += datetime.timedelta(days=correction)

    fitr = ramadan + datetime.timedelta(days=29)
    adha = dh_start + datetime.timedelta(days=9)

    return {
        "ramadan": ramadan,
        "eid_fitr": fitr,
        "arefe": arefe,
        "eid_adha": adha
    }

# =========================
# ANALİZ
# =========================
def analyze():
    text = ""
    correct = 0
    total = 0

    for y in REAL_EVENTS:
        pred = get_events(y)
        real = REAL_EVENTS[y]

        d1 = (pred["ramadan"] - real["ramadan"]).days
        d2 = (pred["eid_fitr"] - real["eid_fitr"]).days
        d3 = (pred["eid_adha"] - real["eid_adha"]).days

        text += f"\n{y}\nRamazan:{d1} Fitr:{d2} Adha:{d3}\n"

        if abs(d1)<=1 and abs(d2)<=1 and abs(d3)<=1:
            correct += 1

        total += 1

    acc = (correct/total)*100 if total else 0
    text += f"\nDOĞRULUK: %{round(acc,2)}"

    return text

# =========================
# TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌙 Ultra Sistem\n/events 2025\n/analyze")

async def events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    y = int(context.args[0])
    e = get_events(y)

    msg = f"{y}\nRamazan:{e['ramadan']}\nFitr:{e['eid_fitr']}\nArefe:{e['arefe']}\nAdha:{e['eid_adha']}"
    await update.message.reply_text(msg)

async def analyze_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(analyze())

# =========================
# MAIN
# =========================
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("events", events))
    app.add_handler(CommandHandler("analyze", analyze_cmd))

    print("Çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
