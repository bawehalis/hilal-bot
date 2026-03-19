import os
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from skyfield.api import load
from skyfield.almanac import find_discrete, moon_phases

TOKEN = os.getenv("TOKEN")
logging.basicConfig(level=logging.INFO)

# =========================
# SKYFIELD
# =========================
ts = load.timescale()
eph = load('de421.bsp')

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
# AY BAŞLANGIÇLARI
# =========================
MONTHS = sorted([
    (nm + timedelta(days=1)).date()
    for nm in NEW_MOONS
])

# =========================
# AY İSİMLERİ
# =========================
AYLAR = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep",
    "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
]

# =========================
# ANCHOR (KRİTİK)
# =========================
ANCHOR_DATE = datetime(2025,3,1).date()  # 1 Ramazan

ANCHOR_INDEX = min(range(len(MONTHS)),
                   key=lambda i: abs((MONTHS[i]-ANCHOR_DATE).days))

# =========================
# HİCRİ HESAP
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
# RAMAZAN BUL
# =========================
def get_ramadan(year):

    for i,m in enumerate(MONTHS):

        diff = i - ANCHOR_INDEX
        ay = (8 + diff) % 12

        if ay == 8 and m.year == year:
            return m

# =========================
# TEST (25 YIL)
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

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = "📊 TEST (25 YIL)\n\n"
    ok = 0
    total = 0

    for y, real in REAL.items():

        real_d = datetime.fromisoformat(real).date()
        model = get_ramadan(y)

        diff = (model - real_d).days

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

print("🚀 DOĞRU SİSTEM AKTİF")
app.run_polling()
