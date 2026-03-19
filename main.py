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

# =========================
# BÖLGELER
# =========================
LOCATIONS = [
    (21.4, 39.8),   # Mekke
    (39.0, 35.0),   # Türkiye
    (35.0, 51.0),   # İran
    (34.5, 69.2),   # Afganistan
]

# =========================
# ANCHOR (ŞU AN DOĞRU)
# =========================
ANCHOR_DATE = datetime(2026, 3, 19, tzinfo=timezone.utc)
ANCHOR_DAY = 30
ANCHOR_MONTH = 9  # Ramazan

# =========================
# 25 YILLIK TEST VERİSİ
# =========================
AREFE_TEST = {
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
# HİLAL HESABI (DÜZELTİLDİ)
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

        # 🔥 GERÇEK KRİTER
        if alt.degrees > 5 and elong > 10:
            return True

    return False

# =========================
# GERİYE
# =========================
def geriye_git(days):
    d = ANCHOR_DATE
    gun = ANCHOR_DAY
    ay = ANCHOR_MONTH
    result = []

    for _ in range(days):
        result.append((d, gun, ay))

        d -= timedelta(days=1)
        gun -= 1

        if gun == 0:
            ay -= 1
            if ay == 0:
                ay = 12

            if hilal_var(d):
                gun = 29
            else:
                gun = 30

    return result

# =========================
# İLERİ
# =========================
def ileri_git(days):
    d = ANCHOR_DATE
    gun = ANCHOR_DAY
    ay = ANCHOR_MONTH
    result = []

    for _ in range(days):
        result.append((d, gun, ay))

        d += timedelta(days=1)
        gun += 1

        if gun > 30:
            if hilal_var(d):
                gun = 1
                ay += 1
                if ay > 12:
                    ay = 1

    return result

# =========================
# YIL
# =========================
def build_year(year):
    data = geriye_git(500) + ileri_git(500)
    months = {}

    for d, gun, ay in data:
        if d.year == year and gun == 1:
            months[ay] = d

    return months

# =========================
# TEST (25 YIL)
# =========================
def test_motor():
    total_error = 0
    count = 0

    print("\n===== 25 YIL TEST =====\n")

    for year, real_str in AREFE_TEST.items():
        months = build_year(year)

        if 12 not in months:
            print(f"{year} ❌ veri yok")
            continue

        model = months[12] + timedelta(days=8)
        real = datetime.fromisoformat(real_str)

        diff = (model.replace(tzinfo=None) - real).days

        total_error += abs(diff)
        count += 1

        status = "🔥" if diff == 0 else "✅" if abs(diff)==1 else "❌"

        print(f"{year} | {diff} gün | {status}")

    print("\n===== SONUÇ =====")
    print(f"Ortalama hata: {total_error/count:.2f} gün")

# =========================
# TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 Hicri Motor Aktif\n\n"
        "/bugun\n"
        "/test"
    )

async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc)

    data = geriye_git(500) + ileri_git(500)

    for d, gun, ay in data:
        if d.date() == today.date():
            aylar = [
                "Muharrem","Safer","Rebiülevvel","Rebiülahir",
                "Cemaziyelevvel","Cemaziyelahir","Recep",
                "Şaban","Ramazan","Şevval","Zilkade","Zilhicce"
            ]

            await update.message.reply_text(
                f"📅 Bugün\n\n"
                f"Miladi: {today.date()}\n"
                f"Hicri: {gun} {aylar[ay-1]}"
            )
            return

async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📊 TEST\n\n"

    for year, real_str in AREFE_TEST.items():
        months = build_year(year)

        if 12 not in months:
            text += f"{year}: ❌\n"
            continue

        model = months[12] + timedelta(days=8)
        real = datetime.fromisoformat(real_str)

        diff = (model.replace(tzinfo=None) - real).days

        text += f"{year}: {diff} gün\n"

    await update.message.reply_text(text)

# =========================
# APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("test", test))

print("🚀 SİSTEM AKTİF")
app.run_polling()
