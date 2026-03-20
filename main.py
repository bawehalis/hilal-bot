import os
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from skyfield.api import load, Topos
from skyfield.almanac import find_discrete, moon_phases

# =========================
# TOKEN
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
# NEW MOON
# =========================
def get_new_moons(start=1995, end=2035):
    t0 = ts.utc(start, 1, 1)
    t1 = ts.utc(end, 12, 31)

    times, phases = find_discrete(t0, t1, moon_phases(eph))

    return [
        t.utc_datetime().replace(tzinfo=timezone.utc)
        for t, p in zip(times, phases)
        if p == 0
    ]

# =========================
# HİLAL GÖRÜNÜRLÜK
# =========================
def hilal_visible(date):
    t = ts.utc(date.year, date.month, date.day, 18)

    e = earth.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    elong = m.separation_from(s).degrees

    loc = earth + Topos(21.4, 39.8)
    alt, _, _ = loc.at(t).observe(moon).apparent().altaz()

    return alt.degrees > 5 and elong > 10

# =========================
# AY BAŞLANGIÇLARI
# =========================
def build_months():
    new_moons = get_new_moons()
    months = []

    for nm in new_moons:
        d1 = (nm + timedelta(days=1)).date()
        d2 = (nm + timedelta(days=2)).date()

        if hilal_visible(d1):
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
# ANCHOR (ZİLHİCCE FIX)
# =========================
ANCHOR_TARGET = datetime(2025, 5, 28).date()

ANCHOR_INDEX = min(
    range(len(MONTHS)),
    key=lambda i: abs((MONTHS[i] - ANCHOR_TARGET).days)
)

# =========================
# HİLAL SAAT FONKSİYONU
# =========================
def hilal_kontrol_saat(date, lat, lon, hour):
    t = ts.utc(date.year, date.month, date.day, hour)

    loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)

    e = loc.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    alt, _, _ = m.altaz()
    elong = m.separation_from(s).degrees

    return alt.degrees, elong

# =========================
# BUGÜN
# =========================
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()

    for i, m in enumerate(MONTHS):
        if m <= today:
            current_month = m
            current_index = i

    gun = (today - current_month).days + 1
    ay_index = (current_index - ANCHOR_INDEX + 11) % 12

    await update.message.reply_text(
        f"📅 Bugün\n\nMiladi: {today}\nHicri: {gun} {AYLAR[ay_index]}"
    )

# =========================
# YIL
# =========================
async def yil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    year = int(context.args[0])

    text = f"📅 {year} Hicri Aylar\n\n"

    for i, m in enumerate(MONTHS):
        if m.year == year:
            ay_index = (i - ANCHOR_INDEX + 11) % 12
            text += f"{AYLAR[ay_index]}: {m}\n"

    await update.message.reply_text(text)

# =========================
# RAMAZAN
# =========================
async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    year = int(context.args[0])

    for i, m in enumerate(MONTHS):
        ay_index = (i - ANCHOR_INDEX + 11) % 12

        if m.year == year and ay_index == 8:
            await update.message.reply_text(
                f"🌙 Ramazan\nBaşlangıç: {m}\nBitiş: {m + timedelta(days=29)}"
            )
            return

# =========================
# AREFE
# =========================
async def arefe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    year = int(context.args[0])

    for i, m in enumerate(MONTHS):
        ay_index = (i - ANCHOR_INDEX + 11) % 12

        if m.year == year and ay_index == 11:
            await update.message.reply_text(
                f"🐑 Arefe: {m + timedelta(days=8)}\nBayram: {m + timedelta(days=9)}"
            )
            return

# =========================
# HİLAL 3 GÜN
# =========================
async def hilal_3gun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    base = datetime.now(timezone.utc).date()

    text = "🌙 3 Gün Analiz\n\n"

    for label, date in {
        "Dün": base - timedelta(days=1),
        "Bugün": base,
        "Yarın": base + timedelta(days=1)
    }.items():

        found = False

        for hour in range(16, 23):
            alt, elong = hilal_kontrol_saat(date, 21.4, 39.8, hour)

            if alt > 5 and elong > 10:
                text += f"{label}: ✅ {hour}:00 UTC\n"
                found = True
                break

        if not found:
            text += f"{label}: ❌\n"

    await update.message.reply_text(text)

# =========================
# HİLAL HARİTA
# =========================
async def hilal_harita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()

    grid = {
        "Amerika": (-20, -60),
        "Afrika": (10, 20),
        "Avrupa": (50, 10),
        "Ortadoğu": (25, 45),
        "Asya": (35, 100),
    }

    text = "🗺️ Hilal Harita\n\n"

    for name, (lat, lon) in grid.items():

        ok = False

        for hour in range(16, 23):
            alt, elong = hilal_kontrol_saat(today, lat, lon, hour)

            if alt > 5 and elong > 10:
                ok = True
                break

        text += f"{name}: {'🟢' if ok else '🔴'}\n"

    await update.message.reply_text(text)

# =========================
# BAYRAM
# =========================
async def bayram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)

    hilal = False

    for hour in range(16, 23):
        alt, elong = hilal_kontrol_saat(tomorrow, 21.4, 39.8, hour)

        if alt > 5 and elong > 10:
            hilal = True
            break

    if hilal:
        text = "🎉 Yarın büyük ihtimalle Bayram"
    else:
        text = "📅 Bayram henüz değil"

    await update.message.reply_text(text)

# =========================
# AI KARAR
# =========================
async def karar(update: Update, context: ContextTypes.DEFAULT_TYPE):

    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)

    countries = {
        "Suudi": (21.4, 39.8),
        "Türkiye": (39.0, 35.0),
        "İran": (35.7, 51.4),
    }

    total = 0
    text = "🧠 Karar Motoru\n\n"

    for name, (lat, lon) in countries.items():

        best = 0

        for hour in range(16, 23):
            alt, elong = hilal_kontrol_saat(tomorrow, lat, lon, hour)

            score = alt + elong

            if score > best:
                best = score

        total += best
        text += f"{name}: {best:.1f}\n"

    confidence = min(int(total), 100)

    result = "🎉 Bayram" if confidence > 60 else "📅 Devam"

    text += f"\nSonuç: {result}\nGüven: %{confidence}"

    await update.message.reply_text(text)

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 Hicri Motor FULL\n\n"
        "/bugun\n/yil 2030\n/ramazan 2030\n/arefe 2030\n"
        "/hilal_3gun\n/hilal_harita\n/bayram\n/karar"
    )

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("yil", yil))
app.add_handler(CommandHandler("ramazan", ramazan))
app.add_handler(CommandHandler("arefe", arefe))
app.add_handler(CommandHandler("hilal_3gun", hilal_3gun))
app.add_handler(CommandHandler("hilal_harita", hilal_harita))
app.add_handler(CommandHandler("bayram", bayram))
app.add_handler(CommandHandler("karar", karar))

print("🚀 FULL SİSTEM AKTİF")
app.run_polling()
