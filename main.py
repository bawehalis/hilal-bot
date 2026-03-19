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
# GERÇEK DATA (25 YIL)
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
# PARAM (İLK AYAR)
# =========================
ALT_T = 3
ELONG_T = 6
AGE_T = 10

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
# HİLAL MODEL
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

    return alt.degrees > ALT_T and elong > ELONG_T and age > AGE_T

# =========================
# AY BAŞLANGIÇ
# =========================
def get_months():

    months = []

    for nm in NEW_MOONS:

        for i in [1,2,3]:
            d = (nm + timedelta(days=i)).date()

            if visible(d, nm):
                months.append(d)
                break
        else:
            months.append((nm + timedelta(days=2)).date())

    return sorted(months)

MONTHS = get_months()

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

    await update.message.reply_text(text)

# =========================
# AYAR ANALİZ
# =========================
async def ayar(update: Update, context: ContextTypes.DEFAULT_TYPE):

    pos = 0
    neg = 0

    for y, real_str in REAL.items():

        real = datetime.fromisoformat(real_str).date()
        model = min(MONTHS, key=lambda x: abs((x-real).days))

        diff = (model - real).days

        if diff > 0:
            pos += 1
        elif diff < 0:
            neg += 1

    text = "⚙️ AYAR ANALİZ\n\n"
    text += f"Geç: {pos}\nErken: {neg}\n\n"

    if pos > neg:
        text += "📉 Geç hesap\nALT düşür\nAGE düşür"
    elif neg > pos:
        text += "📈 Erken hesap\nALT artır\nAGE artır"
    else:
        text += "✅ Dengeli"

    text += f"\n\nMevcut: alt={ALT_T} elong={ELONG_T} age={AGE_T}"

    await update.message.reply_text(text)

# =========================
# HİLAL 3 GÜN
# =========================
async def hilal_3gun(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()

    def check(d):
        nm = min(NEW_MOONS, key=lambda x: abs((x.date()-d)))
        return visible(d, nm)

    d1 = "✅" if check(today- timedelta(days=1)) else "❌"
    d2 = "✅" if check(today) else "❌"
    d3 = "✅" if check(today+ timedelta(days=1)) else "❌"

    text = f"""🌙 3 Gün

Dün: {d1}
Bugün: {d2}
Yarın: {d3}"""

    await update.message.reply_text(text)

# =========================
# KARAR
# =========================
async def karar(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()

    scores = []

    for lat,lon in [(21,39),(39,35),(35,51)]:
        nm = min(NEW_MOONS, key=lambda x: abs((x.date()-today)))
        if visible(today, nm):
            scores.append(1)
        else:
            scores.append(0)

    s = sum(scores)

    if s >= 2:
        msg = "🎉 Bayram"
    else:
        msg = "❌ Değil"

    await update.message.reply_text(f"Karar: {msg}")

# =========================
# BUGÜN
# =========================
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()
    g,a = get_hijri(today)

    await update.message.reply_text(f"{today}\nHicri: {g} {a}")

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("test", test))
app.add_handler(CommandHandler("ayar", ayar))
app.add_handler(CommandHandler("hilal_3gun", hilal_3gun))
app.add_handler(CommandHandler("karar", karar))

print("🚀 FULL SİSTEM AKTİF")
app.run_polling()
