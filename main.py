import os
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
)

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
# PARAM (FINAL AYAR)
# =========================
ALT_T = 2
ELONG_T = 6
AGE_T = 8

# =========================
# REAL DATA
# =========================
REAL = {
    2020:"2020-04-24",
    2021:"2021-04-13",
    2022:"2022-04-02",
    2023:"2023-03-23",
    2024:"2024-03-11",
    2025:"2025-03-01",
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
# MONTHS
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
# BUTTON MENU
# =========================
def menu():

    keyboard = [
        [InlineKeyboardButton("📅 Bugün", callback_data="bugun")],
        [InlineKeyboardButton("📊 Test", callback_data="test")],
        [InlineKeyboardButton("⚙️ Ayar", callback_data="ayar")],
        [InlineKeyboardButton("🌙 3 Gün", callback_data="hilal")],
        [InlineKeyboardButton("🧠 Karar", callback_data="karar")],
    ]

    return InlineKeyboardMarkup(keyboard)

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "🌙 Hicri Hilal Motor\n\nButonlardan seçim yap:",
        reply_markup=menu()
    )

# =========================
# CALLBACK
# =========================
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    today = datetime.now(timezone.utc).date()

    # BUGUN
    if query.data == "bugun":
        g,a = get_hijri(today)
        text = f"📅 Bugün\n\nMiladi: {today}\nHicri: {g} {a}"

    # TEST
    elif query.data == "test":

        text = "📊 TEST\n\n"
        total = 0

        for y, real_str in REAL.items():

            real = datetime.fromisoformat(real_str).date()
            model = min(MONTHS, key=lambda x: abs((x-real).days))

            diff = (model - real).days
            total += abs(diff)

            text += f"{y}: {diff}\n"

        text += f"\nToplam hata: {total}"

    # AYAR
    elif query.data == "ayar":

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

        text = f"""⚙️ AYAR

Geç: {pos}
Erken: {neg}

Öneri:
ALT düşür
AGE düşür

Mevcut: alt={ALT_T} elong={ELONG_T} age={AGE_T}
"""

    # 3 GÜN
    elif query.data == "hilal":

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

    # KARAR
    elif query.data == "karar":

        score = 0

        for lat,lon in [(21,39),(39,35),(35,51)]:
            nm = min(NEW_MOONS, key=lambda x: abs((x.date()-today)))
            if visible(today, nm):
                score += 1

        if score >= 2:
            text = "🎉 Bayram"
        else:
            text = "❌ Değil"

    await query.edit_message_text(text, reply_markup=menu())

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(button))

print("🚀 BUTONLU SİSTEM AKTİF")
app.run_polling()
