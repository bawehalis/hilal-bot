import os
import logging
from datetime import datetime, timezone, timedelta

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 🌙 Astronomi (NASA)
from skyfield.api import load, Topos
from skyfield import almanac

# 📅 Hicri (Umm al-Qura uyumlu)
from hijri_converter import convert

# 🔐 TOKEN
TOKEN = os.getenv("TOKEN")

logging.basicConfig(level=logging.INFO)

# 🌍 Skyfield yükle (ephemeris ilk çalışmada indirir)
ts = load.timescale()
eph = load('de421.bsp')

earth = eph['earth']
moon = eph['moon']
sun = eph['sun']

# 📅 Hicri ay isimleri
months = [
    "Muharrem","Safer","Rebiülevvel","Rebiülahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep","Şaban",
    "Ramazan","Şevval","Zilkade","Zilhicce"
]

# 🌍 Baz şehirler (TR + SA + referanslar)
CITIES = {
    # 🇹🇷
    "istanbul": (41.01, 28.97),
    "ankara": (39.93, 32.85),
    "izmir": (38.42, 27.14),
    "bursa": (40.19, 29.06),
    "antalya": (36.88, 30.70),
    "adana": (37.00, 35.32),
    "gaziantep": (37.07, 37.38),
    "konya": (37.87, 32.48),
    "kayseri": (38.72, 35.48),
    "trabzon": (41.00, 39.72),
    "erzurum": (39.90, 41.27),
    "diyarbakir": (37.91, 40.23),
    "mardin": (37.31, 40.74),
    "van": (38.49, 43.38),
    "batman": (37.88, 41.13),

    # 🇸🇦
    "mekke": (21.39, 39.86),
    "medine": (24.47, 39.61),
    "cidde": (21.54, 39.17),
    "riyad": (24.71, 46.67),

    # 🌍 referans
    "sudan": (15.5, 32.5),
    "iran": (35.0, 51.0),
    "afganistan": (34.5, 69.2),
    "turkiye": (39.0, 35.0),
}

# 🕒 sabit saat dilimleri (DST basit geçiş – yeterli)
TIMEZONES = {
    "istanbul": 3, "ankara": 3, "izmir": 3, "bursa": 3, "antalya": 3,
    "adana": 3, "gaziantep": 3, "konya": 3, "kayseri": 3, "trabzon": 3,
    "erzurum": 3, "diyarbakir": 3, "mardin": 3, "van": 3, "batman": 3,
    "turkiye": 3,

    "mekke": 3, "medine": 3, "cidde": 3, "riyad": 3,

    "iran": 3.5,
    "afganistan": 4.5,
    "sudan": 2
}

# 📅 Hicri
def get_hijri(now):
    g = convert.Gregorian(now.year, now.month, now.day)
    h = g.to_hijri()
    return h.year, h.month, h.day

# 🌙 elongation (Ay-Güneş açısı)
def get_elongation(t):
    e = earth.at(t)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()
    return m.separation_from(s).degrees

# 🌇 o gün için gün batımı (UTC) — Skyfield almanac
def get_sunset_utc(lat, lon, date_utc):
    location = Topos(latitude_degrees=lat, longitude_degrees=lon)
    t0 = ts.utc(date_utc.year, date_utc.month, date_utc.day, 0, 0)
    t1 = ts.utc(date_utc.year, date_utc.month, date_utc.day, 23, 59)

    f = almanac.sunrise_sunset(eph, location)
    times, events = almanac.find_discrete(t0, t1, f)

    # events: 1=Güneş doğdu, 0=Güneş battı
    for ti, ev in zip(times, events):
        if ev == 0:
            return ti  # UTC time (Skyfield Time)
    return None

# 🌙 gün batımında ay yüksekliği + elongation
def visibility_at_sunset(lat, lon, date_utc):
    t_sunset = get_sunset_utc(lat, lon, date_utc)
    if t_sunset is None:
        return None

    loc = earth + Topos(latitude_degrees=lat, longitude_degrees=lon)

    # Ay yüksekliği
    alt, az, dist = loc.at(t_sunset).observe(moon).apparent().altaz()
    altitude = alt.degrees

    # Elongation o anda
    e = earth.at(t_sunset)
    m = e.observe(moon).apparent()
    s = e.observe(sun).apparent()
    elong = m.separation_from(s).degrees

    return {
        "t": t_sunset,
        "alt": altitude,
        "elong": elong
    }

# 🌍 basit görünürlük sınıflandırması (Danjon + pratik eşikler)
def classify(alt, elong):
    if elong < 7 or alt < 0:
        return "❌ Görünmez"
    if alt < 5 or elong < 10:
        return "⚠️ Çok zor"
    if alt < 10 or elong < 15:
        return "⚠️ Zor"
    return "✅ Görülebilir"

# 🌍 ilk görülen bölgeyi bul (batıdan doğuya grid)
def find_first_visibility(date_utc):
    # Afrika batıdan başla (lon: -20 → 60, lat: -20 → 40)
    best = None
    for lon in range(-20, 61, 5):
        for lat in range(-20, 41, 5):
            v = visibility_at_sunset(lat, lon, date_utc)
            if not v:
                continue
            status = classify(v["alt"], v["elong"])
            if status.startswith("✅"):
                # ilk bulunanı döndür (batıdan doğuya taradığımız için)
                best = (lat, lon, v)
                return best
    return None

# 🧮 yardımcı: UTC → yerel saat string
def to_local_str(t_sky, offset_hours):
    dt_utc = t_sky.utc_datetime().replace(tzinfo=timezone.utc)
    local = dt_utc + timedelta(hours=offset_hours)
    return local.strftime("%H:%M")

# 🚀 START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🌙 Hilal Takvim Bot ULTIMATE\n\n"
        "/bugun → Günlük durum\n"
        "/hilal → Genel hilal durumu\n"
        "/dunya → İlk görülen yer + ülke saatleri\n"
        "/konum şehir → Şehirde gün batımında görünürlük\n"
        "/arefe → Arefe mi?\n"
        "/ramazan → Ramazan mı?"
    )

# 📅 BUGÜN
async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone.utc)
    hy, hm, hd = get_hijri(now)

    mesaj = "📅 BUGÜN\n\n"
    mesaj += f"Miladi: {now.date()}\n"
    mesaj += f"Hicri: {hd} {months[hm-1]} {hy}\n\n"

    if hm == 12 and hd == 9:
        mesaj += "🕋 Arefe günü"
    elif hm == 9:
        mesaj += "🌙 Ramazan ayı"
    else:
        mesaj += "Normal gün"

    await update.message.reply_text(mesaj)

# 🌙 GENEL HİLAL
async def hilal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = ts.now()
    elong = get_elongation(t)

    mesaj = "🌙 HİLAL (GENEL)\n\n"
    mesaj += f"Elongation: {elong:.2f}°\n\n"

    if elong < 7:
        mesaj += "❌ Dünya genelinde görünmez"
    elif elong < 10:
        mesaj += "⚠️ Çok zor"
    elif elong < 15:
        mesaj += "⚠️ Zor"
    else:
        mesaj += "✅ Birçok bölgede mümkün"

    await update.message.reply_text(mesaj)

# 🌍 GLOBAL — İLK GÖRÜLME + ÜLKE SAATLERİ
async def dunya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone.utc)
    today = now.date()

    # İlk görülen yer
    first = find_first_visibility(today)

    mesaj = "🌍 GLOBAL HİLAL ANALİZİ (GÜN BATIMI BAZLI)\n\n"

    if not first:
        mesaj += "❌ Bugün dünya genelinde hilal görünmez\n"
        await update.message.reply_text(mesaj)
        return

    lat, lon, v = first
    mesaj += "🌍 İLK GÖRÜLECEK BÖLGE (TAHMİN)\n"
    mesaj += f"📍 Lat/Lon: {lat:.1f}, {lon:.1f}\n"
    mesaj += f"🌙 Yükseklik: {v['alt']:.2f}°\n"
    mesaj += f"🔭 Elongation: {v['elong']:.2f}°\n\n"

    # Ülkeler
    countries = ["mekke", "turkiye", "iran", "afganistan"]
    mesaj += "🌍 ÜLKELERE GÖRE (GÜN BATIMINDA)\n\n"

    for c in countries:
        latc, lonc = CITIES[c]
        res = visibility_at_sunset(latc, lonc, today)
        if not res:
            mesaj += f"{c.upper()} → veri yok\n\n"
            continue

        status = classify(res["alt"], res["elong"])
        tz = TIMEZONES.get(c, 0)
        saat = to_local_str(res["t"], tz)

        mesaj += f"{c.upper()}\n"
        mesaj += f"🕒 Gün batımı: {saat} (yerel)\n"
        mesaj += f"🌙 Yükseklik: {res['alt']:.2f}°\n"
        mesaj += f"🔭 Elongation: {res['elong']:.2f}°\n"
        mesaj += f"{status}\n\n"

    mesaj += "🧠 Not:\n• Hesap gün batımı anına göredir\n• Batıdan doğuya görünürlük azalır"

    await update.message.reply_text(mesaj)

# 🌍 ŞEHİR
async def konum(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        sehir = " ".join(context.args).lower()
        if sehir not in CITIES:
            await update.message.reply_text("❌ Şehir bulunamadı")
            return

        lat, lon = CITIES[sehir]
        today = datetime.now(timezone.utc).date()

        res = visibility_at_sunset(lat, lon, today)
        if not res:
            await update.message.reply_text("❌ Veri alınamadı")
            return

        status = classify(res["alt"], res["elong"])
        tz = TIMEZONES.get(sehir, 0)
        saat = to_local_str(res["t"], tz)

        mesaj = f"🌍 {sehir.upper()}\n\n"
        mesaj += f"🕒 Gün batımı: {saat} (yerel)\n"
        mesaj += f"🌙 Ay yüksekliği: {res['alt']:.2f}°\n"
        mesaj += f"🔭 Elongation: {res['elong']:.2f}°\n\n"
        mesaj += status

        await update.message.reply_text(mesaj)

    except Exception as e:
        await update.message.reply_text("❌ Hata oluştu")

# 🕋 AREFE
async def arefe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone.utc)
    hy, hm, hd = get_hijri(now)

    if hm == 12 and hd == 9:
        await update.message.reply_text("🕋 Bugün arefe")
    else:
        await update.message.reply_text("❌ Bugün arefe değil")

# 🌙 RAMAZAN
async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(timezone.utc)
    hy, hm, hd = get_hijri(now)

    if hm == 9:
        await update.message.reply_text("🌙 Ramazan ayındasın")
    else:
        await update.message.reply_text("Ramazan değil")

# 🚀 APP
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("bugun", bugun))
app.add_handler(CommandHandler("hilal", hilal))
app.add_handler(CommandHandler("dunya", dunya))
app.add_handler(CommandHandler("konum", konum))
app.add_handler(CommandHandler("arefe", arefe))
app.add_handler(CommandHandler("ramazan", ramazan))

print("Bot çalışıyor (ULTIMATE)...")
app.run_polling()
