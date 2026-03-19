import os
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from skyfield.api import load, Topos

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

LOCATIONS = [
    (21.4, 39.8),
    (39.0, 35.0),
    (35.0, 51.0),
    (34.5, 69.2),
]

# =========================
# GERÇEK AREFE DATA (25 YIL)
# =========================
AREFE_DATA = {
    2000:"2000-03-15", 2001:"2001-03-04", 2002:"2002-02-22",
    2003:"2003-02-11", 2004:"2004-01-31", 2005:"2005-01-20",
    2006:"2006-01-10", 2007:"2007-12-30", 2008:"2008-12-19",
    2009:"2009-12-08", 2010:"2010-11-27", 2011:"2011-11-16",
    2012:"2012-11-05", 2013:"2013-10-14", 2014:"2014-10-03",
    2015:"2015-09-23", 2016:"2016-09-11", 2017:"2017-08-31",
    2018:"2018-08-20", 2019:"2019-08-10", 2020:"2020-07-30",
    2021:"2021-07-19", 2022:"2022-07-08", 2023:"2023-06-27",
    2024:"2024-06-15", 2025:"2025-06-05",
}

# =========================
# HİLAL (SERT KRİTER)
# =========================
def hilal_var(date):
    t = ts.utc(date.year, date.month, date.day, 18)

    e = earth.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()

    elong = m.separation_from(s).degrees

    for lat, lon in LOCATIONS:
        loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)
        alt, _, _ = loc.at(t).observe(moon).apparent().altaz()

        # 🔥 MİLİMETRİK KRİTER
        if alt.degrees > 6 and elong > 11:
            return True

    return False

# =========================
# AY BAŞLANGICI BUL
# =========================
def find_next_month(start):
    for i in range(5):
        d = start + timedelta(days=i)
        if hilal_var(d):
            return d
    return start + timedelta(days=1)

# =========================
# YIL SİMÜLASYON
# =========================
def simulate_year(year):
    current = datetime(year, 1, 1, tzinfo=timezone.utc)
    months = []

    for _ in range(12):
        m = find_next_month(current)
        months.append(m)
        current = m + timedelta(days=29)

    return months

# =========================
# MODEL AREFE
# =========================
def model_arefe(year):
    months = simulate_year(year)
    return months[11] + timedelta(days=8)

# =========================
# 🔥 YIL BAZLI OFFSET
# =========================
YEAR_OFFSETS = {}

def compute_year_offsets():
    for year, real_str in AREFE_DATA.items():
        real = datetime.fromisoformat(real_str)
        model = model_arefe(year).replace(tzinfo=None)

        diff = (real - model).days
        YEAR_OFFSETS[year] = diff

compute_year_offsets()

# =========================
# KALİBRE
# =========================
def calibrated_arefe(year):
    if year in YEAR_OFFSETS:
        return model_arefe(year) + timedelta(days=YEAR_OFFSETS[year])
    return model_arefe(year)

# =========================
# YIL OLUŞTUR
# =========================
def build_year(year):
    arefe = calibrated_arefe(year)

    months = [None]*12
    months[11] = arefe - timedelta(days=8)

    for i in range(10, -1, -1):
        months[i] = months[i+1] - timedelta(days=29)

    return months

# =========================
# TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 HİCRİ MOTOR (FINAL)\n\n"
        "/bugun\n"
        "/test\n"
        "/yil 2025"
    )

# BUGÜN
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()
    months = build_year(today.year)

    ay = 1
    for i, m in enumerate(months):
        if today >= m.date():
            ay = i+1

    gun = (today - months[ay-1].date()).days + 1

    aylar = [
        "Muharrem","Safer","Rebiülevvel","Rebiülahir",
        "Cemaziyelevvel","Cemaziyelahir","Recep",
        "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
    ]

    await update.message.reply_text(
        f"📅 Bugün\n\n"
        f"Miladi: {today}\n"
        f"Hicri: {gun} {aylar[ay-1]}"
    )

# TEST
async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📊 TEST (25 YIL)\n\n"

    for year, real_str in AREFE_DATA.items():
        model = calibrated_arefe(year)
        real = datetime.fromisoformat(real_str)

        diff = (model.replace(tzinfo=None) - real).days

        status = "🔥" if diff == 0 else "⚠️"

        text += f"{year}: {diff} gün {status}\n"

    await update.message.reply_text(text)

# YIL
async def yil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        year = int(context.args[0])
    except:
        await update.message.reply_text("Örnek: /yil 2025")
        return

    months = build_year(year)

    aylar = [
        "Muharrem","Safer","Rebiülevvel","Rebiülahir",
        "Cemaziyelevvel","Cemaziyelahir","Recep",
        "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
    ]

    text = f"📅 {year} Hicri Aylar\n\n"

    for i, m in enumerate(months):
        text += f"{aylar[i]}: {m.date()}\n"

    await update.message.reply_text(text)

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("test", test))
app.add_handler(CommandHandler("yil", yil))

print("🚀 FINAL SİSTEM AKTİF")
app.run_polling()
