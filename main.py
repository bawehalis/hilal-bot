import os
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from skyfield.api import load, Topos
from skyfield.almanac import find_discrete, moon_phases, sunset_sunrise

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
# GLOBAL GRID (YOĞUN)
# =========================
GRID = []

for lat in range(-40, 50, 10):
    for lon in range(-80, 100, 20):
        GRID.append((lat, lon))

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
# GÜNEŞ BATIMI BUL
# =========================
def get_sunset(date, lat, lon):

    t0 = ts.utc(date.year, date.month, date.day)
    t1 = ts.utc(date.year, date.month, date.day, 23)

    location = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)

    f = sunset_sunrise(eph, location)
    times, events = find_discrete(t0, t1, f)

    for t, e in zip(times, events):
        if e == 1:  # sunset
            return t.utc_datetime()

    return None

# =========================
# HİLAL PARAM
# =========================
def hilal_param(time, lat, lon):

    loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)

    e = loc.at(ts.utc(time))
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    alt, _, _ = m.altaz()
    elong = m.separation_from(s).degrees

    return alt.degrees, elong

# =========================
# ULTIMATE SKOR
# =========================
def visibility_score(alt, elong, age):

    if elong < 7:
        return -10

    # 🔥 gelişmiş model
    score = (alt * 0.5) + (elong * 0.3) + (age * 0.2)

    return score

# =========================
# GLOBAL ANALİZ (SUNSET BAZLI)
# =========================
def global_visibility(date, new_moon):

    best = None
    best_score = -999

    for lat, lon in GRID:

        sunset = get_sunset(date, lat, lon)

        if not sunset:
            continue

        alt, elong = hilal_param(sunset, lat, lon)

        age = (sunset - new_moon).total_seconds() / 3600

        score = visibility_score(alt, elong, age)

        if score > best_score:
            best_score = score
            best = (lat, lon, sunset, alt, elong, age)

    return best, best_score

# =========================
# AY BAŞLANGIÇ
# =========================
def build_months():

    new_moons = get_new_moons()
    months = []

    for nm in new_moons:

        d1 = (nm + timedelta(days=1)).date()
        d2 = (nm + timedelta(days=2)).date()

        _, score1 = global_visibility(d1, nm)

        if score1 > 7:
            months.append(d1)
        else:
            months.append(d2)

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
# BUGÜN
# =========================
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()

    idx = None

    for i, m in enumerate(MONTHS):
        if m <= today:
            idx = i

    start = MONTHS[idx]

    gun = (today - start).days + 1
    ay = (idx - ANCHOR_INDEX + 11) % 12

    await update.message.reply_text(
        f"📅 Bugün\n\nMiladi: {today}\nHicri: {gun} {AYLAR[ay]}"
    )

# =========================
# GLOBAL ANALİZ KOMUTU
# =========================
async def hilal(update: Update, context: ContextTypes.DEFAULT_TYPE):

    today = datetime.now(timezone.utc).date()

    nm_list = get_new_moons()
    nm = min(nm_list, key=lambda x: abs((x.date() - today)))

    best, score = global_visibility(today, nm)

    lat, lon, sunset, alt, elong, age = best

    text = f"🌍 GLOBAL HİLAL V4\n\n"
    text += f"📅 {today}\n\n"
    text += f"📍 İlk güçlü nokta:\n"
    text += f"{lat},{lon}\n"
    text += f"🕒 Sunset: {sunset.strftime('%H:%M')} UTC\n\n"
    text += f"🌙 Alt: {alt:.2f}\n"
    text += f"🌙 Elong: {elong:.2f}\n"
    text += f"🌙 Age: {age:.1f} saat\n"
    text += f"📊 Skor: {score:.2f}\n\n"

    if score > 7:
        text += "✅ Hilal GÖRÜLEBİLİR"
    else:
        text += "❌ Hilal GÖRÜLEMEZ"

    await update.message.reply_text(text)

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 ULTIMATE V4 Hicri Motor\n\n"
        "/bugun\n/hilal"
    )

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("hilal", hilal))

print("🚀 ULTIMATE V4 AKTİF")
app.run_polling()
