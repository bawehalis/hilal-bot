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
# 25 YIL GERÇEK DATA
# =========================
REAL = {
    2000:"2000-11-27",2001:"2001-11-17",2002:"2002-11-06",
    2003:"2003-10-27",2004:"2004-10-16",2005:"2005-10-05",
    2006:"2006-09-24",2007:"2007-09-13",2008:"2008-09-01",
    2009:"2009-08-22",2010:"2010-08-11",2011:"2011-08-01",
    2012:"2012-07-21",2013:"2013-07-10",2014:"2014-06-29",
    2015:"2015-06-18",2016:"2016-06-06",2017:"2017-05-27",
    2018:"2018-05-17",2019:"2019-05-06",2020:"2020-04-24",
    2021:"2021-04-13",2022:"2022-04-02",2023:"2023-03-23",
    2024:"2024-03-11",2025:"2025-03-01",
}

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
# HİLAL MODEL (OPTIMIZE EDİLECEK)
# =========================
def visible(date, nm, ALT_T=3, ELONG_T=6, AGE_T=10):

    t = ts.utc(date.year, date.month, date.day, 18)

    loc = earth + Topos(21.4,39.8)

    e = loc.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    alt, _, _ = m.altaz()
    elong = m.separation_from(s).degrees

    age = (datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc) - nm).total_seconds()/3600

    return alt.degrees > ALT_T and elong > ELONG_T and age > AGE_T

# =========================
# AY BAŞLANGIÇ
# =========================
def build_months(ALT_T, ELONG_T, AGE_T):

    months = []

    for nm in NEW_MOONS:

        for i in [1,2,3]:

            d = (nm + timedelta(days=i)).date()

            if visible(d, nm, ALT_T, ELONG_T, AGE_T):
                months.append(d)
                break
        else:
            months.append((nm + timedelta(days=2)).date())

    return sorted(months)

# =========================
# TEST + OPTIMIZATION
# =========================
def optimize():

    best = None
    best_error = 9999

    for alt in [2,3,4,5]:
        for elong in [5,6,7,8]:
            for age in [8,10,12]:

                months = build_months(alt, elong, age)

                error = 0

                for year, real_str in REAL.items():

                    real = datetime.fromisoformat(real_str).date()

                    # Ramazan bul
                    closest = min(months, key=lambda x: abs((x-real).days))

                    error += abs((closest - real).days)

                if error < best_error:
                    best_error = error
                    best = (alt, elong, age)

    return best, best_error

ALT_T, ELONG_T, AGE_T = optimize()[0]

MONTHS = build_months(ALT_T, ELONG_T, AGE_T)

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
# TEST
# =========================
async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = "📊 TEST (25 YIL)\n\n"
    ok = 0
    total = 0

    for y, real_str in REAL.items():

        real = datetime.fromisoformat(real_str).date()

        model = min(MONTHS, key=lambda x: abs((x-real).days))

        diff = (model - real).days

        if diff == 0:
            text += f"{y}: 0 🔥\n"
            ok += 1
        else:
            text += f"{y}: {diff} ❗\n"
            total += abs(diff)

    text += f"\n🎯 {ok}/26 doğru"
    text += f"\n📉 hata: {total}"
    text += f"\n⚙️ alt={ALT_T} elong={ELONG_T} age={AGE_T}"

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
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("test", test))

print("🚀 25 YIL OPTİMİZE SİSTEM AKTİF")
app.run_polling()
