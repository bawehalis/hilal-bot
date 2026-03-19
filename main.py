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
# ASTRONOMİ YÜKLE
# =========================
ts = load.timescale()
eph = load('de421.bsp')

earth = eph['earth']
moon = eph['moon']
sun = eph['sun']

# =========================
# AY İSİMLERİ
# =========================
AYLAR = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep",
    "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
]

# =========================
# NEW MOON LİSTESİ
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
# HİLAL PARAMETRELERİ
# =========================
def hilal_param(date, lat=21.4, lon=39.8, hour=18):
    t = ts.utc(date.year, date.month, date.day, hour)

    loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)

    e = loc.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    alt, _, _ = m.altaz()
    elong = m.separation_from(s).degrees

    return alt.degrees, elong

# =========================
# ULTIMATE SCORE (KALİBRE)
# =========================
def hilal_score(date, new_moon_dt):
    alt, elong = hilal_param(date)

    # Ay yaşı (saat)
    moon_age = (datetime(date.year, date.month, date.day, tzinfo=timezone.utc) - new_moon_dt).total_seconds() / 3600

    # 🔥 KALİBRE EDİLMİŞ AĞIRLIKLAR
    score = (alt * 0.5) + (elong * 0.3) + (moon_age * 0.2)

    return score, alt, elong, moon_age

# =========================
# AY BAŞLANGIÇLARI (ULTIMATE)
# =========================
def build_months():
    new_moons = get_new_moons()
    months = []

    for nm in new_moons:
        d1 = (nm + timedelta(days=1)).date()
        d2 = (nm + timedelta(days=2)).date()

        score, alt, elong, age = hilal_score(d1, nm)

        # 🔥 KARAR EŞİĞİ (DATADAN KALİBRE)
        if score > 7:
            months.append(d1)
        else:
            months.append(d2)

    return sorted(months)

MONTHS = build_months()

# =========================
# ANCHOR (ZİLHİCCE 2025)
# =========================
ANCHOR_TARGET = datetime(2025, 5, 29).date()

ANCHOR_INDEX = min(
    range(len(MONTHS)),
    key=lambda i: abs((MONTHS[i] - ANCHOR_TARGET).days)
)

# =========================
# BUGÜN
# =========================
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()

    current_index = None

    for i, m in enumerate(MONTHS):
        if m <= today:
            current_index = i

    if current_index is None:
        await update.message.reply_text("Hata")
        return

    start = MONTHS[current_index]

    gun = (today - start).days + 1
    ay_index = (current_index - ANCHOR_INDEX + 11) % 12

    await update.message.reply_text(
        f"📅 Bugün\n\nMiladi: {today}\nHicri: {gun} {AYLAR[ay_index]}"
    )

# =========================
# YIL
# =========================
async def yil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    year = int(context.args[0])

    start = datetime(year,1,1).date()
    end = datetime(year,12,31).date()

    text = f"📅 {year} Hicri Aylar\n\n"

    for i, m in enumerate(MONTHS):
        if start <= m <= end:
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

        score, alt, elong, age = hilal_score(date, datetime.now(timezone.utc))

        if score > 7:
            text += f"{label}: ✅ (score={score:.1f})\n"
        else:
            text += f"{label}: ❌ (score={score:.1f})\n"

    await update.message.reply_text(text)

# =========================
# BAYRAM TAHMİN
# =========================
async def bayram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tomorrow = datetime.now(timezone.utc).date() + timedelta(days=1)

    score, _, _, _ = hilal_score(tomorrow, datetime.now(timezone.utc))

    if score > 7:
        text = f"🎉 Yarın Bayram olabilir\n(score={score:.1f})"
    else:
        text = f"📅 Bayram değil\n(score={score:.1f})"

    await update.message.reply_text(text)

# =========================
# AI KARAR MOTORU
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
            alt, elong = hilal_param(tomorrow, lat, lon, hour)
            score = (alt * 0.5) + (elong * 0.5)

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
        "🌙 ULTIMATE Hicri Motor\n\n"
        "/bugun\n/yil 2025\n/ramazan 2025\n/arefe 2025\n"
        "/hilal_3gun\n/bayram\n/karar"
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
app.add_handler(CommandHandler("bayram", bayram))
app.add_handler(CommandHandler("karar", karar))

print("🚀 ULTIMATE MODEL AKTİF")
app.run_polling()
