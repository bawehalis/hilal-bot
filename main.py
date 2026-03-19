import os
import logging
from datetime import datetime, timedelta, timezone

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from skyfield.api import load, Topos

# =========================
# 🔐 TOKEN
# =========================
TOKEN = os.getenv("TOKEN")

logging.basicConfig(level=logging.INFO)

# =========================
# 🌙 ASTRONOMİ
# =========================
ts = load.timescale()
eph = load('de421.bsp')

earth = eph['earth']
moon = eph['moon']
sun = eph['sun']

# =========================
# 📍 REFERANS BÖLGELER
# =========================
LOCATIONS = [
    (21.4, 39.8),   # Mekke
    (39.0, 35.0),   # Türkiye
    (35.0, 51.0),   # İran
    (34.5, 69.2),   # Afganistan
]

# =========================
# 🔥 ANCHOR (ŞU AN)
# =========================
ANCHOR_DATE = datetime(2026, 3, 19, tzinfo=timezone.utc)
ANCHOR_DAY = 30
ANCHOR_MONTH = 9  # Ramazan

# =========================
# 📊 TEST VERİSİ (AREFE)
# =========================
AREFE_TEST = {
    2023: "2023-06-27",
    2024: "2024-06-15",
    2025: "2025-06-05",
}

# =========================
# 🌙 HİLAL HESAP
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

        if alt.degrees > 0 and elong > 7:
            return True

    return False

# =========================
# 🔥 GERİYE GİT
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

            # hilale göre ay uzunluğu
            if hilal_var(d):
                gun = 29
            else:
                gun = 30

    return result

# =========================
# 🔥 İLERİ GİT
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
# 📅 YIL OLUŞTUR
# =========================
def build_year(year):
    data = geriye_git(400) + ileri_git(400)

    months = {}

    for d, gun, ay in data:
        if d.year == year and gun == 1:
            months[ay] = d

    return months

# =========================
# 🧪 TEST SİSTEMİ
# =========================
def test_motor():
    print("\n===== TEST =====\n")

    for year, real_str in AREFE_TEST.items():
        months = build_year(year)

        if 12 not in months:
            print(f"{year} ❌ Zilhicce bulunamadı")
            continue

        zilhicce = months[12]
        arefe = zilhicce + timedelta(days=8)

        real = datetime.fromisoformat(real_str)

        diff = (arefe.replace(tzinfo=None) - real).days

        print(f"{year}")
        print(f"Gerçek: {real.date()}")
        print(f"Model : {arefe.date()}")
        print(f"Fark  : {diff} gün\n")

# =========================
# 🚀 TELEGRAM
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 Hicri Motor Aktif\n\n"
        "/bugun\n"
        "/test"
    )

# BUGÜN
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc)

    data = geriye_git(400) + ileri_git(400)

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

# TEST
async def test(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = ""

    for year, real_str in AREFE_TEST.items():
        months = build_year(year)

        if 12 not in months:
            result += f"{year} ❌\n"
            continue

        arefe = months[12] + timedelta(days=8)
        real = datetime.fromisoformat(real_str)

        diff = (arefe.replace(tzinfo=None) - real).days

        result += f"{year}: {diff} gün\n"

    await update.message.reply_text(result)

# =========================
# 🚀 APP
# =========================
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("test", test))

print("SİSTEM AKTİF 🚀")
app.run_polling()
