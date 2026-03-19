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
# GERÇEK DATA
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
# NEW MOON
# =========================
def get_new_moons():
    t0 = ts.utc(1995,1,1)
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
def hilal_visible(date, nm, alt_limit, elong_limit):

    t = ts.utc(date.year, date.month, date.day, 18)
    loc = earth + Topos(21.4,39.8)

    e = loc.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    alt, _, _ = m.altaz()
    elong = m.separation_from(s).degrees

    age = (datetime.combine(date, datetime.min.time(), tzinfo=timezone.utc) - nm).total_seconds()/3600

    return alt.degrees > alt_limit and elong > elong_limit and age > 12

# =========================
# RAMAZAN MODEL
# =========================
def get_ramadan(year, alt_limit, elong_limit, shift):

    target = datetime(year,3,15,tzinfo=timezone.utc)

    nm = min(NEW_MOONS, key=lambda x: abs(x-target))

    for i in [1,2,3]:
        d = (nm + timedelta(days=i+shift)).date()

        if hilal_visible(d, nm, alt_limit, elong_limit):
            return d

    return (nm + timedelta(days=2)).date()

# =========================
# OPTİMİZASYON
# =========================
def optimize():

    best = (0,0,0,999)

    for alt in [3,4,5,6]:
        for elong in [6,7,8,9]:
            for shift in [-1,0,1]:

                error = 0

                for y, real in REAL.items():

                    real_d = datetime.fromisoformat(real).date()
                    model = get_ramadan(y, alt, elong, shift)

                    error += abs((model - real_d).days)

                if error < best[3]:
                    best = (alt, elong, shift, error)

    return best

ALT, ELONG, SHIFT, ERR = optimize()

# =========================
# TEST
# =========================
async def test25(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = "📊 TEST (25 YIL)\n\n"
    ok = 0
    total = 0

    for y, real in REAL.items():

        real_d = datetime.fromisoformat(real).date()
        model = get_ramadan(y, ALT, ELONG, SHIFT)

        diff = (model - real_d).days

        if diff == 0:
            text += f"{y}: 0 🔥\n"
            ok += 1
        else:
            text += f"{y}: {diff} ❗\n"
            total += abs(diff)

    text += f"\n🎯 {ok}/26 doğru"
    text += f"\n📉 hata: {total}"
    text += f"\n⚙️ alt={ALT} elong={ELONG} shift={SHIFT}"

    await update.message.reply_text(text)

# =========================
# BUGÜN
# =========================
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()
    ramazan = get_ramadan(today.year, ALT, ELONG, SHIFT)

    gun = (today - ramazan).days + 1

    await update.message.reply_text(
        f"📅 Bugün\n\nMiladi: {today}\nHicri: {gun} Ramazan"
    )

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("test25", test25))

print(f"🚀 OPTIMIZED alt={ALT} elong={ELONG} shift={SHIFT}")
app.run_polling()
