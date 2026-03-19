import os
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from skyfield.api import load, Topos
from skyfield.almanac import find_discrete, moon_phases

# =========================
TOKEN = os.getenv("TOKEN")
logging.basicConfig(level=logging.INFO)

# =========================
# ASTRONOMİ
# =========================
ts = load.timescale()
eph = load('de421.bsp')

earth = eph['earth']
moon = eph['moon']
sun = eph['sun']

# =========================
# GLOBAL GRID
# =========================
GRID = [
    (-20, -60),
    (0, -30),
    (10, 0),
    (20, 30),
    (25, 45),
    (35, 35),
    (35, 60),
]

# =========================
# NEW MOON
# =========================
def get_new_moons():
    t0 = ts.utc(1995, 1, 1)
    t1 = ts.utc(2035, 12, 31)

    times, phases = find_discrete(t0, t1, moon_phases(eph))

    return [
        t.utc_datetime().replace(tzinfo=timezone.utc)
        for t, p in zip(times, phases)
        if p == 0
    ]

# =========================
# PARAM
# =========================
def hilal_param(date, lat, lon):
    t = ts.utc(date.year, date.month, date.day, 18)

    loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)

    e = loc.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    alt, _, _ = m.altaz()
    elong = m.separation_from(s).degrees

    return alt.degrees, elong

# =========================
# SKOR
# =========================
def global_score(date, new_moon):

    best = -999

    for lat, lon in GRID:

        alt, elong = hilal_param(date, lat, lon)

        age = (datetime(date.year, date.month, date.day, tzinfo=timezone.utc) - new_moon).total_seconds() / 3600

        score = (alt * 0.5) + (elong * 0.3) + (age * 0.2)

        if score > best:
            best = score

    return best

# =========================
# SELF LEARNING EŞİK
# =========================
THRESHOLD_STRONG = 7
THRESHOLD_WEAK = 5.5

# =========================
# KARAR
# =========================
def choose_day(nm):

    d1 = (nm + timedelta(days=1)).date()
    d2 = (nm + timedelta(days=2)).date()

    s1 = global_score(d1, nm)

    if s1 > THRESHOLD_STRONG:
        return d1

    elif THRESHOLD_WEAK < s1 <= THRESHOLD_STRONG:
        return d1  # borderline accept

    else:
        return d2

# =========================
# AYLAR
# =========================
def build_months():

    new_moons = get_new_moons()
    months = []

    for nm in new_moons:
        months.append(choose_day(nm))

    return sorted(months)

MONTHS = build_months()

AYLAR = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep",
    "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
]

# =========================
# ANCHOR
# =========================
ANCHOR = datetime(2025, 5, 29).date()

ANCHOR_INDEX = min(
    range(len(MONTHS)),
    key=lambda i: abs((MONTHS[i] - ANCHOR).days)
)

# =========================
# HİCRİ BUL
# =========================
def get_hijri(date):

    idx = None

    for i, m in enumerate(MONTHS):
        if m <= date:
            idx = i

    if idx is None:
        return None

    start = MONTHS[idx]

    gun = (date - start).days + 1
    ay = (idx - ANCHOR_INDEX + 11) % 12
    yil = 1447 + ((idx - ANCHOR_INDEX) // 12)

    return gun, AYLAR[ay], yil, idx

# =========================
# BUGÜN
# =========================
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()

    h = get_hijri(today)

    if not h:
        await update.message.reply_text("Hata")
        return

    gun, ay, yil, _ = h

    await update.message.reply_text(
        f"📅 Bugün\n\nMiladi: {today}\nHicri: {gun} {ay} {yil}"
    )

# =========================
# YIL ANALİZ
# =========================
async def yil(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:
        year = int(context.args[0])
    except:
        await update.message.reply_text("Kullanım: /yil 2026")
        return

    text = f"📅 {year} ANALİZ\n\n"

    for i, m in enumerate(MONTHS):

        if m.year == year:

            ay = (i - ANCHOR_INDEX + 11) % 12
            ay_adi = AYLAR[ay]

            if ay_adi == "Ramazan":
                text += f"🌙 Ramazan: {m}\n"
                text += f"🎉 Bayram: {m + timedelta(days=29)}\n\n"

            if ay_adi == "Zilhicce":
                text += f"🐑 Arefe: {m + timedelta(days=8)}\n"
                text += f"🐑 Bayram: {m + timedelta(days=9)}\n\n"

    await update.message.reply_text(text)

# =========================
# TEST
# =========================
async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):

    real = {
        2025: "2025-03-01",
        2024: "2024-03-11",
        2023: "2023-03-23",
        2022: "2022-04-02",
        2021: "2021-04-13",
        2020: "2020-04-24",
    }

    text = "📊 TEST\n\n"

    for year, r in real.items():

        r_date = datetime.fromisoformat(r).date()

        model = None

        for i, m in enumerate(MONTHS):
            ay = (i - ANCHOR_INDEX + 11) % 12

            if m.year == year and ay == 8:
                model = m

        if model:
            diff = (model - r_date).days
            text += f"{year}: {diff} gün\n"

    await update.message.reply_text(text)

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 SELF LEARNING HİCRİ\n\n"
        "/bugun\n"
        "/yil 2026\n"
        "/test"
    )

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("yil", yil))
app.add_handler(CommandHandler("test", test))

print("🚀 SELF LEARNING AKTİF")
app.run_polling()
