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
# 🔥 HİLAL MODELİ (SON DENGE)
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

    # 🔥 SON DENGE MODELİ
    if alt >= 4 and elong >= 5:
        return True

    if alt >= 6 and elong >= 4:
        return True

    if age >= 12 and elong >= 4:
        return True

    return False

# =========================
# AY BAŞLANGIÇ
# =========================
def get_months():

    months = []

    for nm in NEW_MOONS:

        for i in range(1,4):
            d = (nm + timedelta(days=i)).date()

            if visible(d, nm):
                months.append(d)
                break
        else:
            months.append((nm + timedelta(days=2)).date())

    return sorted(months)

MONTHS = get_months()

# =========================
# HİCRİ
# =========================
AYLAR = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep",
    "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
]

# 🔥 STABLE ANCHOR (DOĞRU NOKTA)
ANCHOR_DATE = datetime(2025,3,1).date()

ANCHOR_INDEX = min(range(len(MONTHS)),
                   key=lambda i: abs((MONTHS[i]-ANCHOR_DATE).days))

# =========================
# HİCRİ BUL
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

    return {
        "ramazan": ramazan,
        "bayram": ramazan + timedelta(days=29),
        "arefe": zilhicce + timedelta(days=8),
        "kurban": zilhicce + timedelta(days=9)
    }

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
# YIL
# =========================
async def yil(update: Update, context: ContextTypes.DEFAULT_TYPE):

    y = int(context.args[0])
    d = analyze_year(y)

    await update.message.reply_text(
f"""📅 {y}

🌙 Ramazan: {d['ramazan']}
🎉 Bayram: {d['bayram']}

🐑 Arefe: {d['arefe']}
🐑 Kurban: {d['kurban']}"""
    )

# =========================
# TEST (25 YIL)
# =========================
async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):

    REAL = {
        2000:"2000-11-27",2001:"2001-11-17",2002:"2002-11-06",
        2003:"2003-10-27",2004:"2004-10-16",2005:"2005-10-05",
        2006:"2006-09-24",2007:"2007-09-13",2008:"2008-09-01",
        2009:"2009-08-22",2010:"2010-08-12",2011:"2011-08-01",
        2012:"2012-07-21",2013:"2013-07-10",2014:"2014-06-29",
        2015:"2015-06-18",2016:"2016-06-06",2017:"2017-05-27",
        2018:"2018-05-17",2019:"2019-05-06",2020:"2020-04-24",
        2021:"2021-04-13",2022:"2022-04-02",2023:"2023-03-23",
        2024:"2024-03-11",2025:"2025-03-01"
    }

    text = "📊 TEST (25 YIL)\n\n"
    total = 0
    ok = 0

    for year, real_str in REAL.items():

        real = datetime.fromisoformat(real_str).date()
        model = analyze_year(year)["ramazan"]

        diff = (model - real).days
        total += abs(diff)

        if diff == 0:
            text += f"{year}: 0 🔥\n"
            ok += 1
        else:
            text += f"{year}: {diff} ❗\n"

    text += f"\n🎯 {ok}/26 doğru"
    text += f"\n📉 hata: {total}"

    await update.message.reply_text(text)

# =========================
# 3 GÜN ANALİZ
# =========================
async def hilal_3gun(update: Update, context: ContextTypes.DEFAULT_TYPE):

    t = datetime.now(timezone.utc).date()

    def c(d):
        nm = max([x for x in NEW_MOONS if x.date() <= d])
        return "✅" if visible(d,nm) else "❌"

    text = f"""🌙 3 Gün Analiz

Dün: {c(t-timedelta(days=1))}
Bugün: {c(t)}
Yarın: {c(t+timedelta(days=1))}"""

    await update.message.reply_text(text)

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
"""🚀 Hicri Motor FINAL

/bugun
/yil 2025
/test
/hilal_3gun"""
    )

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("yil", yil))
app.add_handler(CommandHandler("test", test))
app.add_handler(CommandHandler("hilal_3gun", hilal_3gun))

print("🚀 FINAL BALANCED MOTOR AKTİF")
app.run_polling()
