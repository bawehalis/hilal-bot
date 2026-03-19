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
# DATASET
# =========================
REAL_DATA = {
    2000: "2000-11-27", 2001: "2001-11-17", 2002: "2002-11-06",
    2003: "2003-10-27", 2004: "2004-10-16", 2005: "2005-10-05",
    2006: "2006-09-24", 2007: "2007-09-13", 2008: "2008-09-01",
    2009: "2009-08-22", 2010: "2010-08-11", 2011: "2011-08-01",
    2012: "2012-07-21", 2013: "2013-07-10", 2014: "2014-06-29",
    2015: "2015-06-18", 2016: "2016-06-06", 2017: "2017-05-27",
    2018: "2018-05-17", 2019: "2019-05-06", 2020: "2020-04-24",
    2021: "2021-04-13", 2022: "2022-04-02", 2023: "2023-03-23",
    2024: "2024-03-11", 2025: "2025-03-01",
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
# HİLAL SKOR
# =========================
def hilal_score(date, nm):

    t = ts.utc(date.year, date.month, date.day, 18)
    loc = earth + Topos(latitude_degrees=21.4, longitude_degrees=39.8)

    e = loc.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    alt, _, _ = m.altaz()
    elong = m.separation_from(s).degrees

    age = (datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc) - nm).total_seconds()/3600

    return alt.degrees*0.5 + elong*0.3 + age*0.2

# =========================
# SELF LEARNING CALIBRATION
# =========================
def train_model():

    best_threshold = 5.5
    best_shift = 0
    best_error = 999

    for threshold in [4.5, 5.0, 5.5, 6.0]:
        for shift in [-1, 0, 1]:

            total = 0

            for year, real_str in REAL_DATA.items():

                real = datetime.fromisoformat(real_str).date()
                nm = [x for x in NEW_MOONS if x.year == year][0]

                d1 = (nm + timedelta(days=1+shift)).date()
                d2 = (nm + timedelta(days=2+shift)).date()

                s1 = hilal_score(d1, nm)

                if s1 > threshold:
                    model = d1
                else:
                    model = d2

                total += abs((model - real).days)

            if total < best_error:
                best_error = total
                best_threshold = threshold
                best_shift = shift

    return best_threshold, best_shift

THRESHOLD, SHIFT = train_model()

# =========================
# AY BAŞLANGIÇ
# =========================
def get_month_starts():

    starts = []

    for nm in NEW_MOONS:

        d1 = (nm + timedelta(days=1+SHIFT)).date()
        d2 = (nm + timedelta(days=2+SHIFT)).date()

        s1 = hilal_score(d1, nm)

        if s1 > THRESHOLD:
            starts.append(d1)
        else:
            starts.append(d2)

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
# TEST
# =========================
async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = "📊 TEST (AI)\n\n"
    total = 0
    ok = 0

    for year, real_str in REAL_DATA.items():

        real = datetime.fromisoformat(real_str).date()

        nm = [x for x in NEW_MOONS if x.year == year][0]

        d1 = (nm + timedelta(days=1+SHIFT)).date()
        d2 = (nm + timedelta(days=2+SHIFT)).date()

        s1 = hilal_score(d1, nm)

        model = d1 if s1 > THRESHOLD else d2

        diff = (model - real).days

        if diff == 0:
            text += f"{year}: 0 🔥\n"
            ok += 1
        else:
            text += f"{year}: {diff} ❗\n"
            total += abs(diff)

    text += f"\n🎯 {ok}/26 doğru"
    text += f"\n📉 hata: {total}"
    text += f"\n⚙️ threshold={THRESHOLD} shift={SHIFT}"

    await update.message.reply_text(text)

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
        "🚀 AI HİLAL MOTOR\n\n"
        "/bugun\n"
        "/test"
    )

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("test", test))

print(f"🚀 AI AKTİF | T={THRESHOLD} SHIFT={SHIFT}")
app.run_polling()
