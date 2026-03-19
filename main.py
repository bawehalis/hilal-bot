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
# DATASET (TEST)
# =========================
REAL_RAMAZAN = {
    2000: "2000-11-27",
    2001: "2001-11-17",
    2002: "2002-11-06",
    2003: "2003-10-27",
    2004: "2004-10-16",
    2005: "2005-10-05",
    2006: "2006-09-24",
    2007: "2007-09-13",
    2008: "2008-09-01",
    2009: "2009-08-22",
    2010: "2010-08-12",
    2011: "2011-08-01",
    2012: "2012-07-21",
    2013: "2013-07-10",
    2014: "2014-06-29",
    2015: "2015-06-18",
    2016: "2016-06-06",
    2017: "2017-05-27",
    2018: "2018-05-17",
    2019: "2019-05-06",
    2020: "2020-04-24",
    2021: "2021-04-13",
    2022: "2022-04-02",
    2023: "2023-03-23",
    2024: "2024-03-11",
    2025: "2025-03-01",
}

# =========================
# NEW MOONS
# =========================
def get_new_moons():
    t0 = ts.utc(2000, 1, 1)
    t1 = ts.utc(2035, 12, 31)

    times, phases = find_discrete(t0, t1, moon_phases(eph))

    return [
        t.utc_datetime().replace(tzinfo=timezone.utc)
        for t, p in zip(times, phases)
        if p == 0
    ]

NEW_MOONS = get_new_moons()

# =========================
# HİLAL MODEL
# =========================
def visible(date, nm):

    t = ts.utc(date.year, date.month, date.day, 18)

    loc = earth + Topos(latitude_degrees=21.4, longitude_degrees=39.8)

    e = loc.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    alt, _, _ = m.altaz()
    elong = m.separation_from(s).degrees

    age = (datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc) - nm).total_seconds()/3600

    if alt.degrees < 0 or elong < 6 or age < 12:
        return False

    score = alt.degrees*0.4 + elong*0.4 + age*0.2

    return score > 10

# =========================
# AY BAŞLANGIÇ
# =========================
def get_month_starts():

    starts = []

    for nm in NEW_MOONS:

        for i in range(1,4):
            d = (nm + timedelta(days=i)).date()

            if visible(d, nm):
                starts.append(d)
                break
        else:
            starts.append((nm + timedelta(days=2)).date())

    return sorted(starts)

MONTHS = get_month_starts()

# =========================
# AYLAR
# =========================
AYLAR = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep",
    "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
]

# =========================
# ANCHOR
# =========================
ANCHOR_DATE = datetime(2025,3,1).date()

ANCHOR_INDEX = min(range(len(MONTHS)),
                   key=lambda i: abs((MONTHS[i]-ANCHOR_DATE).days))

# =========================
# HİCRİ
# =========================
def get_hijri(date):

    idx = None

    for i,m in enumerate(MONTHS):
        if m <= date:
            idx = i

    if idx is None:
        return 0,"?"

    diff = idx - ANCHOR_INDEX
    ay = (8 + diff) % 12

    start = MONTHS[idx]
    gun = (date - start).days + 1

    return gun, AYLAR[ay]

# =========================
# YIL ANALİZ
# =========================
def analyze_year(year):

    target = datetime(year,6,1).date()

    ramazan = []
    zilhicce = []

    for i,m in enumerate(MONTHS):

        diff = i - ANCHOR_INDEX
        ay = (8 + diff) % 12

        if ay == 8:
            ramazan.append(m)

        if ay == 11:
            zilhicce.append(m)

    ramazan = min(ramazan, key=lambda x: abs(x-target))
    zilhicce = min(zilhicce, key=lambda x: abs(x-target))

    next_ram = min([x for x in ramazan if x>ramazan], default=ramazan+timedelta(days=30))

    return {
        "ramazan": ramazan,
        "bayram": next_ram,
        "arefe": zilhicce + timedelta(days=8),
        "kurban": zilhicce + timedelta(days=9)
    }

# =========================
# TEST
# =========================
async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = "📊 25 YIL TEST\n\n"

    total_error = 0
    exact = 0

    for year, real_str in REAL_RAMAZAN.items():

        real = datetime.fromisoformat(real_str).date()
        model = analyze_year(year)["ramazan"]

        diff = (model - real).days
        total_error += abs(diff)

        if diff == 0:
            text += f"{year}: 0 🔥\n"
            exact += 1
        else:
            text += f"{year}: {diff} ❗\n"

    text += f"\n🎯 {exact}/26 doğru"
    text += f"\n📉 hata: {total_error}"

    await update.message.reply_text(text)

# =========================
# BOT
# =========================
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()

    g,a = get_hijri(today)

    await update.message.reply_text(f"Miladi: {today}\nHicri: {g} {a}")

async def yil(update: Update, context: ContextTypes.DEFAULT_TYPE):

    y = int(context.args[0])
    d = analyze_year(y)

    text = f"{y}\nRamazan: {d['ramazan']}\nBayram: {d['bayram']}\nArefe: {d['arefe']}"
    await update.message.reply_text(text)

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("yil", yil))
app.add_handler(CommandHandler("test", test))

print("🚀 TESTLİ AKTİF")
app.run_polling()
