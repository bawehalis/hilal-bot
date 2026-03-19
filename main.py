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

# =========================
# NEW MOONS
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
# AY BAŞLANGIÇ
# =========================
def get_month_starts():

    starts = []

    for nm in NEW_MOONS:

        # klasik: 1 gün sonrası
        start = (nm + timedelta(days=1)).date()

        starts.append(start)

    return sorted(starts)

MONTHS = get_month_starts()

# =========================
# AY İSİMLERİ
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
# RAMAZAN BUL
# =========================
def get_ramadan(year):

    for i,m in enumerate(MONTHS):

        diff = i - ANCHOR_INDEX
        ay = (8 + diff) % 12

        if ay == 8 and m.year == year:
            return m

    return None

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
# TEST
# =========================
REAL_DATA = {
    2020: "2020-04-24",
    2021: "2021-04-13",
    2022: "2022-04-02",
    2023: "2023-03-23",
    2024: "2024-03-11",
    2025: "2025-03-01",
}

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = "📊 TEST\n\n"
    total = 0

    for year, real_str in REAL_DATA.items():

        real = datetime.fromisoformat(real_str).date()
        model = get_ramadan(year)

        diff = (model - real).days

        text += f"{year}: {diff}\n"
        total += abs(diff)

    text += f"\nToplam hata: {total}"

    await update.message.reply_text(text)

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 STABLE MODEL\n\n"
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

print("🚀 STABLE AKTİF")
app.run_polling()
