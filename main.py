import os
import datetime
import numpy as np

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# =========================
# CONFIG
# =========================
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("TOKEN bulunamadı")

ANCHOR_AREFE = datetime.date(1995, 5, 9)

# Hicri artık yıl indexleri
LEAP_YEARS = [2,5,7,10,13,16,18,21,24,26,29]

# =========================
# GERÇEK DATA (örnek)
# =========================
REAL_EVENTS = {
    2023: {"ramadan": datetime.date(2023,3,23), "eid_fitr": datetime.date(2023,4,21), "eid_adha": datetime.date(2023,6,28)},
    2024: {"ramadan": datetime.date(2024,3,11), "eid_fitr": datetime.date(2024,4,10), "eid_adha": datetime.date(2024,6,16)},
    2025: {"ramadan": datetime.date(2025,3,1),  "eid_fitr": datetime.date(2025,3,30), "eid_adha": datetime.date(2025,6,6)},
}

# =========================
# HİCRİ YIL HESAP
# =========================

def is_leap(year):
    cycle = (year - 1995) % 30
    return cycle in LEAP_YEARS


def estimate_arefe(year):
    date = ANCHOR_AREFE

    if year >= 1995:
        for y in range(1995, year):
            date += datetime.timedelta(days=355 if is_leap(y) else 354)
    else:
        for y in range(year, 1995):
            date -= datetime.timedelta(days=355 if is_leap(y) else 354)

    return date

# =========================
# HİCRİ OLAYLAR
# =========================

def get_events(year):

    arefe = estimate_arefe(year)

    # Zilhicce başlangıcı
    dh_start = arefe - datetime.timedelta(days=8)

    # Ramazan (9 ay geri ≈ 266 gün)
    ramadan = dh_start - datetime.timedelta(days=266)

    # küçük düzeltme (29/30 farkı)
    ramadan += datetime.timedelta(days=np.random.choice([-1,0,1]))

    # Bayramlar
    fitr = ramadan + datetime.timedelta(days=29)
    adha = dh_start + datetime.timedelta(days=9)

    return {
        "ramadan": ramadan,
        "eid_fitr": fitr,
        "arefe": arefe,
        "eid_adha": adha
    }

# =========================
# ANALİZ
# =========================

def analyze_30():
    report = ""
    correct = 0
    total = 0

    for y in range(2000, 2026):
        pred = get_events(y)

        report += f"\n📅 {y}\n"

        if y in REAL_EVENTS:
            real = REAL_EVENTS[y]

            d1 = (pred["ramadan"] - real["ramadan"]).days
            d2 = (pred["eid_fitr"] - real["eid_fitr"]).days
            d3 = (pred["eid_adha"] - real["eid_adha"]).days

            report += f"Ramazan: {pred['ramadan']} ({d1})\n"
            report += f"Fitr: {pred['eid_fitr']} ({d2})\n"
            report += f"Adha: {pred['eid_adha']} ({d3})\n"

            if abs(d1)<=1 and abs(d2)<=1 and abs(d3)<=1:
                correct += 1

            total += 1

    acc = (correct/total)*100 if total else 0
    report += f"\n📊 DOĞRULUK: %{round(acc,2)}"

    return report

# =========================
# TELEGRAM
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 Hicri Sistem\n\n"
        "/events 2025\n"
        "/analyze"
    )

async def events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        year = int(context.args[0])
        e = get_events(year)

        msg = f"📅 {year}\n"
        msg += f"🌙 Ramazan: {e['ramadan']}\n"
        msg += f"🎉 Fitr: {e['eid_fitr']}\n"
        msg += f"🕋 Arefe: {e['arefe']}\n"
        msg += f"🐑 Kurban: {e['eid_adha']}"

        await update.message.reply_text(msg)

    except:
        await update.message.reply_text("Format: /events 2025")

async def analyze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    r = analyze_30()
    for i in range(0, len(r), 3500):
        await update.message.reply_text(r[i:i+3500])

# =========================
# MAIN
# =========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("events", events))
    app.add_handler(CommandHandler("analyze", analyze))

    print("Bot çalışıyor...")
    app.run_polling()

if __name__ == "__main__":
    main()
