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
    raise ValueError("TOKEN env bulunamadı")

THRESHOLD = 0.6

WEIGHTS = {
    "MECCA": 0.5,
    "ANKARA": 0.3,
    "TEHRAN": 0.2
}

LOCATIONS = {
    "MECCA": Topos(21.3891, 39.8579),
    "ANKARA": Topos(39.9334, 32.8597),
    "TEHRAN": Topos(35.6892, 51.3890),
}

# =========================
# DATASET (genişlet)
# =========================
REAL_EVENTS = {
    2023: {"ramadan": datetime.date(2023,3,23), "eid_fitr": datetime.date(2023,4,21), "eid_adha": datetime.date(2023,6,28)},
    2024: {"ramadan": datetime.date(2024,3,11), "eid_fitr": datetime.date(2024,4,10), "eid_adha": datetime.date(2024,6,16)},
    2025: {"ramadan": datetime.date(2025,3,1),  "eid_fitr": datetime.date(2025,3,30), "eid_adha": datetime.date(2025,6,6)},
}

# =========================
# SKYFIELD INIT
# =========================
ts = load.timescale()
eph = load('de421.bsp')

earth = eph['earth']
moon = eph['moon']
sun = eph['sun']

# =========================
# ASTRONOMİ
# =========================

def moon_age(date):
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


def get_params(date, location):
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


def score(age, alt, elong):
    a = min(age / 24, 1)
    b = min(elong / 12, 1)
    c = min(max(alt, 0) / 10, 1)
    d = min(age / 30, 1)

    return 0.35*a + 0.25*b + 0.20*c + 0.20*d

# =========================
# AY BAŞLANGICI
# =========================

def find_start(date):
    for i in range(3):
        d = date + datetime.timedelta(days=i)
        total = 0

        for name, loc in LOCATIONS.items():
            age = moon_age(d)
            alt, elong = get_params(d, loc)
            s = score(age, alt, elong)

            total += s * WEIGHTS[name]

        if total >= THRESHOLD:
            return d, total

    return date + datetime.timedelta(days=1), total

# =========================
# HİCRİ OLAYLAR
# =========================

def generate_months(year):
    date = datetime.date(year,1,1)
    months = []

    for _ in range(12):
        start, _ = find_start(date)
        months.append(start)
        date = start + datetime.timedelta(days=29)

    return months


def get_events(year):
    m = generate_months(year)

    ramadan = m[8]
    fitr = m[9]
    dh = m[11]

    arefe = dh + datetime.timedelta(days=8)
    adha = dh + datetime.timedelta(days=9)

    return {
        "ramadan": ramadan,
        "eid_fitr": fitr,
        "arefe": arefe,
        "eid_adha": adha
    }

# =========================
# ANALİZ
# =========================

def analyze_30():
    report = ""
    correct = 0
    total = 0

    for y in range(2000, 2026):
        pred = get_events(y)

        report += f"\n📅 {y}\n"

        if y in REAL_EVENTS:
            real = REAL_EVENTS[y]

            d1 = (pred["ramadan"] - real["ramadan"]).days
            d2 = (pred["eid_fitr"] - real["eid_fitr"]).days
            d3 = (pred["eid_adha"] - real["eid_adha"]).days

            report += f"Ramazan: {pred['ramadan']} ({d1})\n"
            report += f"Fitr: {pred['eid_fitr']} ({d2})\n"
            report += f"Adha: {pred['eid_adha']} ({d3})\n"

            if abs(d1)<=1 and abs(d2)<=1 and abs(d3)<=1:
                correct += 1

            total += 1

    acc = (correct/total)*100 if total else 0
    report += f"\n📊 DOĞRULUK: %{round(acc,2)}"

    return report

# =========================
# ML TRAIN
# =========================

def loss():
    total = 0
    count = 0

    for y in REAL_EVENTS:
        pred = get_events(y)
        real = REAL_EVENTS[y]

        total += abs((pred["ramadan"] - real["ramadan"]).days)
        total += abs((pred["eid_fitr"] - real["eid_fitr"]).days)
        total += abs((pred["eid_adha"] - real["eid_adha"]).days)

        count += 3

    return total / count if count else 999


def train():
    global THRESHOLD, WEIGHTS

    best = loss()

    for _ in range(30):
        new_t = THRESHOLD + np.random.uniform(-0.02,0.02)

        new_w = {k: max(0, v+np.random.uniform(-0.1,0.1)) for k,v in WEIGHTS.items()}
        s = sum(new_w.values())
        new_w = {k:v/s for k,v in new_w.items()}

        old_t, old_w = THRESHOLD, WEIGHTS.copy()

        THRESHOLD = new_t
        WEIGHTS = new_w

        l = loss()

        if l < best:
            best = l
        else:
            THRESHOLD, WEIGHTS = old_t, old_w

    return best

# =========================
# TELEGRAM (ASYNC)
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🌙 Sistem aktif\n/ay\n/events\n/analyze\n/train")

async def ay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        y,m,d = map(int, context.args[0].split("-"))
        date = datetime.date(y,m,d)

        s, sc = find_start(date)

        await update.message.reply_text(f"{s}\nSkor:{round(sc,3)}")
    except:
        await update.message.reply_text("Format: /ay 2026-03-20")

async def events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    y = int(context.args[0])
    e = get_events(y)

    msg = f"{y}\nRamazan:{e['ramadan']}\nFitr:{e['eid_fitr']}\nArefe:{e['arefe']}\nAdha:{e['eid_adha']}"
    await update.message.reply_text(msg)

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = analyze_30()
    for i in range(0,len(r),3500):
        await update.message.reply_text(r[i:i+3500])

async def train_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    l = train()
    await update.message.reply_text(f"Training OK\nLoss:{round(l,3)}\nT:{round(THRESHOLD,3)}\nW:{WEIGHTS}")

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ay", ay))
    app.add_handler(CommandHandler("events", events))
    app.add_handler(CommandHandler("analyze", analyze))
    app.add_handler(CommandHandler("train", train_cmd))

    print("Bot çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
