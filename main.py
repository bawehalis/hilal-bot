“””
╔══════════════════════════════════════════════════════════╗
║         HİCRİ TAKVİM TELEGRAM BOTU — ZİRVE SÜRÜM        ║
║  Astronomik hilal hesabı + tam Hicri takvim sistemi      ║
╚══════════════════════════════════════════════════════════╝
“””

import os
import logging
import math
from datetime import datetime, timedelta, timezone, date

from telegram import Update
from telegram.ext import (
ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters
)

from skyfield.api import load, wgs84
from skyfield.almanac import find_discrete, moon_phases, sunrise_sunset

# ══════════════════════════════════════════════

# LOGGING & TOKEN

# ══════════════════════════════════════════════

logging.basicConfig(
level=logging.INFO,
format=”%(asctime)s [%(levelname)s] %(message)s”
)
logger = logging.getLogger(**name**)

TOKEN = os.getenv(“TOKEN”)
if not TOKEN:
raise EnvironmentError(“❌ TOKEN ortam değişkeni tanımlı değil!”)

# ══════════════════════════════════════════════

# SKYFIELD — EPHEMERİS

# ══════════════════════════════════════════════

ts = load.timescale()

# de421.bsp yoksa indir — startup’ta bir kez

try:
eph = load(‘de421.bsp’)
logger.info(“✅ de421.bsp yüklendi.”)
except Exception:
logger.info(“⬇️  de421.bsp indiriliyor…”)
from skyfield.api import Loader
sky_load = Loader(’.’)
eph = sky_load(‘de421.bsp’)
logger.info(“✅ de421.bsp indirildi ve yüklendi.”)

earth = eph[‘earth’]
moon  = eph[‘moon’]
sun   = eph[‘sun’]

# ══════════════════════════════════════════════

# KONUMLAR (wgs84 ile doğru kullanım)

# ══════════════════════════════════════════════

LOCATIONS = {
“Mekke”:   wgs84.latlon(21.4225, 39.8262),
“Ankara”:  wgs84.latlon(39.9334, 32.8597),
“Tahran”:  wgs84.latlon(35.6892, 51.3890),
“Kahire”:  wgs84.latlon(30.0444, 31.2357),
“İstanbul”:wgs84.latlon(41.0082, 28.9784),
}

# ══════════════════════════════════════════════

# YENİ AYLAR

# ══════════════════════════════════════════════

def get_new_moons(start: int = 1993, end: int = 2037) -> list:
t0 = ts.utc(start, 1, 1)
t1 = ts.utc(end, 12, 31)
times, phases = find_discrete(t0, t1, moon_phases(eph))
return [
t.utc_datetime().replace(tzinfo=timezone.utc)
for t, p in zip(times, phases)
if p == 0  # 0 = Yeni Ay
]

NEW_MOONS = get_new_moons()
logger.info(f”✅ {len(NEW_MOONS)} yeni ay hesaplandı.”)

# ══════════════════════════════════════════════

# GÜNEŞ BATIŞI HESABI

# ══════════════════════════════════════════════

def get_sunset(loc, year: int, month: int, day: int) -> float:
“”“UTC saat olarak güneş batış zamanı döner. Bulunamazsa 18.0 döner.”””
try:
t0 = ts.utc(year, month, day, 12)
t1 = ts.utc(year, month, day, 23, 59)
f  = sunrise_sunset(eph, loc)
times, events = find_discrete(t0, t1, f)
for t, e in zip(times, events):
if e == 0:  # 0 = batış
return t.utc_datetime().hour + t.utc_datetime().minute / 60
return 18.0
except Exception:
return 18.0

# ══════════════════════════════════════════════

# HİLAL SKORU — GELİŞMİŞ MODEL

# ══════════════════════════════════════════════

def hilal_score(check_date: date, nm: datetime) -> float:
“””
Hilal görünürlük skoru (yüksek = daha görünür).
- Güneş batışından sonraki pencerede değerlendirir
- İrtifa, elongasyon, yaş, aydınlık yüzdesi kullanır
- Negatif irtifa durumları dışlanır
“””
total = 0.0
count = 0

```
for loc_name, loc in LOCATIONS.items():
    sunset_hour = get_sunset(loc, check_date.year, check_date.month, check_date.day)

    # Güneş batışından 30dk sonra → +2 saat pencere
    for minute_offset in range(30, 150, 15):
        hour_frac  = sunset_hour + minute_offset / 60
        hour       = int(hour_frac)
        minute     = int((hour_frac - hour) * 60)

        if hour >= 24:
            break

        t = ts.utc(check_date.year, check_date.month, check_date.day, hour, minute)

        obs = (earth + loc).at(t)
        m_app = obs.observe(moon).apparent()
        s_app = obs.observe(sun).apparent()

        alt_m, az_m, _  = m_app.altaz()
        alt_s, _, _     = s_app.altaz()
        elong           = m_app.separation_from(s_app).degrees

        alt_deg = alt_m.degrees

        # Ay ufkun altındaysa bu ölçümü atla
        if alt_deg <= 0:
            continue

        # Ay yaşı (saat)
        age_hours = (
            datetime.combine(check_date, datetime.min.time(), tzinfo=timezone.utc) - nm
        ).total_seconds() / 3600

        # Aydınlanma yüzdesi (yaklaşık)
        illum = ((1 - math.cos(math.radians(elong))) / 2) * 100

        score = (
            alt_deg   * 1.5   +   # irtifa en kritik faktör
            elong     * 0.8   +   # güneş-ay açısı
            age_hours * 0.05  +   # ay yaşı
            illum     * 0.3       # aydınlık yüzdesi
        )

        total += score
        count += 1

return total / count if count > 0 else 0.0
```

# ══════════════════════════════════════════════

# AY BAŞI KARAR MEKANİZMASI

# ══════════════════════════════════════════════

def find_month_start(nm: datetime) -> date:
“””
Yeni aya göre hilal görünürlüğünü değerlendir,
1. veya 2. günü ay başı olarak belirle.
“””
d1 = nm.date() + timedelta(days=1)
d2 = nm.date() + timedelta(days=2)

```
s1 = hilal_score(d1, nm)
s2 = hilal_score(d2, nm)

# 1. gün güçlü görünürlük
if s1 >= 18.0:
    return d1

# 2. gün belirgin üstünlük
if s1 > 0 and (s2 - s1) / max(s1, 1) > 0.25:
    return d2

# Varsayılan: 1. gün (İslam'da şüphe halinde önceki ayı tamamla diyenler var
# ama hesap takviminde d1 döndürmek standart)
return d1
```

# ══════════════════════════════════════════════

# TAKVİM İNŞASI

# ══════════════════════════════════════════════

def build_months() -> list:
return sorted([find_month_start(nm) for nm in NEW_MOONS])

logger.info(“⏳ Ay başları hesaplanıyor (ilk çalıştırmada biraz sürebilir)…”)
MONTHS = build_months()
logger.info(f”✅ {len(MONTHS)} ay başı hesaplandı.”)

# ══════════════════════════════════════════════

# HİCRİ AY İSİMLERİ

# ══════════════════════════════════════════════

AYLAR = [
“Muharrem”, “Safer”, “Rebiülevvel”, “Rebiülahir”,
“Cemaziyelevvel”, “Cemaziyelahir”, “Recep”,
“Şaban”, “Ramazan”, “Şevval”, “Zilkade”, “Zilhicce”
]

# Özel günler: (ay_index, gün) → isim

OZEL_GUNLER = {
(0, 10):  “🔴 Aşure Günü”,
(1, 12):  “🕌 Mevlid Kandili (Rebiülevvel 12)”,
(6,  1):  “🕯️  Regaib Kandili (Recep 1. Cuma — yaklaşık)”,
(6, 27):  “🌟 Miraç Kandili”,
(7, 15):  “🕯️  Berat Kandili”,
(8,  1):  “🌙 Ramazan Başlangıcı”,
(8, 27):  “✨ Kadir Gecesi (yaklaşık)”,
(9,  1):  “🎉 Ramazan Bayramı 1. Günü”,
(9,  2):  “🎉 Ramazan Bayramı 2. Günü”,
(9,  3):  “🎉 Ramazan Bayramı 3. Günü”,
(11, 9):  “🕋 Arefe Günü”,
(11,10):  “🎊 Kurban Bayramı 1. Günü”,
(11,11):  “🎊 Kurban Bayramı 2. Günü”,
(11,12):  “🎊 Kurban Bayramı 3. Günü”,
(11,13):  “🎊 Kurban Bayramı 4. Günü”,
}

# ══════════════════════════════════════════════

# ANCHOR — 1 Ramazan 1446 = 1 Mart 2025

# ══════════════════════════════════════════════

ANCHOR_TARGET = datetime(2025, 3, 1).date()
ANCHOR_INDEX  = min(
range(len(MONTHS)),
key=lambda i: abs((MONTHS[i] - ANCHOR_TARGET).days)
)
logger.info(f”✅ Anchor: MONTHS[{ANCHOR_INDEX}] = {MONTHS[ANCHOR_INDEX]} (hedef: {ANCHOR_TARGET})”)

# ══════════════════════════════════════════════

# HİCRİ HESAP FONKSİYONLARI

# ══════════════════════════════════════════════

def get_hijri(check_date: date) -> tuple:
“””(gün, ay_adı, ay_index, hicri_yıl) döner.”””
current = None
for i, m in enumerate(MONTHS):
if m <= check_date:
current = (m, i)

```
if not current:
    return 0, "?", -1, 0

start, idx = current
gun       = (check_date - start).days + 1
ay_index  = (idx - ANCHOR_INDEX) % 12

# Hicri yıl: anchor = 1446 Ramazan → Ramazan'ın bulunduğu yılı baz al
# ANCHOR_INDEX, 1 Ramazan 1446'ya karşılık gelir
# Her 12 ayda bir yıl artar
hicri_yil = 1446 + (idx - ANCHOR_INDEX) // 12

return gun, AYLAR[ay_index], ay_index, hicri_yil
```

def date_from_hijri(hicri_yil: int, ay_index: int, gun: int):
“”“Hicri tarihten miladi tarih döner. Bulamazsa None.”””
# ANCHOR_INDEX = 1 Ramazan 1446 = ay_index 8
# idx = ANCHOR_INDEX + (hicri_yil - 1446)*12 + (ay_index - 8)
offset = (hicri_yil - 1446) * 12 + (ay_index - 8)
target_idx = ANCHOR_INDEX + offset

```
if target_idx < 0 or target_idx >= len(MONTHS):
    return None

start = MONTHS[target_idx]
return start + timedelta(days=gun - 1)
```

def find_month_date(year_miladi: int, ay_index: int):
“”“Verilen miladi yılda ve ay indexinde ay başını bul.”””
for i, m in enumerate(MONTHS):
idx = (i - ANCHOR_INDEX) % 12
if idx == ay_index and abs(m.year - year_miladi) <= 1:
# yıl eşleşmesi için ay başının yakın olması yeterli
if m.year == year_miladi or (ay_index <= 1 and m.year == year_miladi - 1):
return m, i
# daha geniş arama
for i, m in enumerate(MONTHS):
idx = (i - ANCHOR_INDEX) % 12
if idx == ay_index and m.year == year_miladi:
return m, i
return None, None

# ══════════════════════════════════════════════

# GERÇEK VERİ — ANALİZ İÇİN

# ══════════════════════════════════════════════

REAL_RAMADAN = {
1995: date(1995, 2, 1),  1996: date(1996, 1, 22),
1997: date(1997, 1, 11), 1998: date(1998, 12, 20),
1999: date(1999, 12, 9), 2000: date(2000, 11, 27),
2001: date(2001, 11, 16),2002: date(2002, 11, 6),
2003: date(2003, 10, 27),2004: date(2004, 10, 15),
2005: date(2005, 10, 4), 2006: date(2006, 9, 24),
2007: date(2007, 9, 13), 2008: date(2008, 9, 1),
2009: date(2009, 8, 22), 2010: date(2010, 8, 11),
2011: date(2011, 8, 1),  2012: date(2012, 7, 20),
2013: date(2013, 7, 9),  2014: date(2014, 6, 28),
2015: date(2015, 6, 18), 2016: date(2016, 6, 6),
2017: date(2017, 5, 27), 2018: date(2018, 5, 16),
2019: date(2019, 5, 6),  2020: date(2020, 4, 24),
2021: date(2021, 4, 13), 2022: date(2022, 4, 2),
2023: date(2023, 3, 23), 2024: date(2024, 3, 11),
2025: date(2025, 3, 1),
}

# ══════════════════════════════════════════════

# YARDIMCI: GİRDİ DOĞRULAMA

# ══════════════════════════════════════════════

def parse_year(args, min_y=1995, max_y=2037) -> int:
if not args:
raise ValueError(“Lütfen bir yıl girin. Örnek: /ramazan 2027”)
try:
y = int(args[0])
except ValueError:
raise ValueError(f”’{args[0]}’ geçerli bir yıl değil.”)
if not (min_y <= y <= max_y):
raise ValueError(f”Yıl {min_y}–{max_y} arasında olmalıdır.”)
return y

def parse_date_arg(args) -> date:
if not args:
raise ValueError(“Lütfen tarih girin. Örnek: /miladiden 2026-03-20”)
try:
return datetime.strptime(args[0], “%Y-%m-%d”).date()
except ValueError:
raise ValueError(f”Tarih formatı YYYY-AA-GG olmalı. Örnek: 2026-03-20”)

async def reply_error(update: Update, msg: str):
await update.message.reply_text(f”⚠️ {msg}”)

# ══════════════════════════════════════════════

# KOMUT: /start

# ══════════════════════════════════════════════

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
text = (
“🌙 *Hicri Takvim Botu — Zirve Sürüm*\n\n”
“📋 *Komutlar:*\n”
“▸ /bugun — Bugünün Hicri tarihi\n”
“▸ /yil 2027 — Yıl bazlı Hicri takvim\n”
“▸ /ramazan 2027 — Ramazan başlangıcı\n”
“▸ /arefe 2027 — Arefe & Kurban Bayramı\n”
“▸ /bayramlar 2027 — Tüm dini günler\n”
“▸ /kacgun 2027 — Ramazana kaç gün kaldı\n”
“▸ /hilal — Bugün hilal görünür mü?\n”
“▸ /miladiden 2026-03-20 — Miladi→Hicri\n”
“▸ /hicridenmiladi 15 Ramazan 1446 — Hicri→Miladi\n”
“▸ /analiz — Doğruluk analizi (Ramazan 1995–2025)\n”
“▸ /karsilastir 2026 — Ayları karşılaştır\n”
“▸ /yardim — Bu menü\n”
)
await update.message.reply_text(text, parse_mode=“Markdown”)

# ══════════════════════════════════════════════

# KOMUT: /bugun

# ══════════════════════════════════════════════

async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
today = datetime.now(timezone.utc).date()
gun, ay_adi, ay_idx, hicri_yil = get_hijri(today)

```
ozel = OZEL_GUNLER.get((ay_idx, gun), "")
ozel_line = f"\n🔔 *{ozel}*" if ozel else ""

text = (
    f"📅 *Bugünün Tarihi*\n\n"
    f"🗓 Miladi : `{today}`\n"
    f"🌙 Hicri  : `{gun} {ay_adi} {hicri_yil}`"
    f"{ozel_line}"
)
await update.message.reply_text(text, parse_mode="Markdown")
```

# ══════════════════════════════════════════════

# KOMUT: /yil <miladi_yil>

# ══════════════════════════════════════════════

async def yil(update: Update, context: ContextTypes.DEFAULT_TYPE):
try:
year = parse_year(context.args)
except ValueError as e:
return await reply_error(update, str(e))

```
lines = [f"📅 *{year} Yılı Hicri Ay Başları*\n"]
found = False

for i, m in enumerate(MONTHS):
    if m.year == year or (m.year == year - 1 and m.month == 12):
        idx  = (i - ANCHOR_INDEX) % 12
        hyil = 1446 + (i - ANCHOR_INDEX) // 12
        lines.append(f"• {AYLAR[idx]} {hyil}: `{m}`")
        found = True

if not found:
    lines.append("Bu yıl için veri bulunamadı.")

await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
```

# ══════════════════════════════════════════════

# KOMUT: /ramazan <yil>

# ══════════════════════════════════════════════

async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
try:
year = parse_year(context.args)
except ValueError as e:
return await reply_error(update, str(e))

```
m, _ = find_month_date(year, 8)  # 8 = Ramazan
if m:
    bitis = m + timedelta(days=29)
    text  = (
        f"🌙 *Ramazan {year}*\n\n"
        f"▸ Başlangıç : `{m}`\n"
        f"▸ Bitiş (29.gün) : `{bitis}`\n"
        f"▸ Kadir Gecesi (~27): `{m + timedelta(days=26)}`"
    )
else:
    text = f"⚠️ {year} için Ramazan verisi bulunamadı."

await update.message.reply_text(text, parse_mode="Markdown")
```

# ══════════════════════════════════════════════

# KOMUT: /arefe <yil>

# ══════════════════════════════════════════════

async def arefe(update: Update, context: ContextTypes.DEFAULT_TYPE):
try:
year = parse_year(context.args)
except ValueError as e:
return await reply_error(update, str(e))

```
m, _ = find_month_date(year, 11)  # 11 = Zilhicce
if m:
    arefe_gunu   = m + timedelta(days=8)   # Zilhicce 9
    bayram_1     = m + timedelta(days=9)   # Zilhicce 10
    bayram_2     = m + timedelta(days=10)
    bayram_3     = m + timedelta(days=11)
    bayram_4     = m + timedelta(days=12)
    text = (
        f"🕋 *Kurban Bayramı {year}*\n\n"
        f"▸ Arefe      : `{arefe_gunu}`\n"
        f"▸ Bayram 1   : `{bayram_1}`\n"
        f"▸ Bayram 2   : `{bayram_2}`\n"
        f"▸ Bayram 3   : `{bayram_3}`\n"
        f"▸ Bayram 4   : `{bayram_4}`"
    )
else:
    text = f"⚠️ {year} için Zilhicce verisi bulunamadı."

await update.message.reply_text(text, parse_mode="Markdown")
```

# ══════════════════════════════════════════════

# KOMUT: /bayramlar <yil>

# ══════════════════════════════════════════════

async def bayramlar(update: Update, context: ContextTypes.DEFAULT_TYPE):
try:
year = parse_year(context.args)
except ValueError as e:
return await reply_error(update, str(e))

```
OZEL_LISTE = [
    (0, 10,  "🔴 Aşure Günü"),
    (1, 12,  "🕌 Mevlid Kandili"),
    (6, 27,  "🌟 Miraç Kandili"),
    (7, 15,  "🕯️  Berat Kandili"),
    (8,  1,  "🌙 Ramazan Başlangıcı"),
    (8, 27,  "✨ Kadir Gecesi (~)"),
    (9,  1,  "🎉 Ramazan Bayramı 1. Gün"),
    (9,  2,  "🎉 Ramazan Bayramı 2. Gün"),
    (9,  3,  "🎉 Ramazan Bayramı 3. Gün"),
    (11, 9,  "🕋 Arefe Günü"),
    (11,10,  "🎊 Kurban Bayramı 1. Gün"),
    (11,11,  "🎊 Kurban Bayramı 2. Gün"),
    (11,12,  "🎊 Kurban Bayramı 3. Gün"),
    (11,13,  "🎊 Kurban Bayramı 4. Gün"),
]

lines = [f"🗓 *{year} Dini Günler Takvimi*\n"]
found_any = False

for ay_idx, gun, isim in OZEL_LISTE:
    m, _ = find_month_date(year, ay_idx)
    if m:
        hedef = m + timedelta(days=gun - 1)
        if hedef.year == year:
            lines.append(f"• `{hedef}` — {isim}")
            found_any = True

if not found_any:
    lines.append("Bu yıl için veri bulunamadı.")

await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
```

# ══════════════════════════════════════════════

# KOMUT: /kacgun [yil]

# ══════════════════════════════════════════════

async def kacgun(update: Update, context: ContextTypes.DEFAULT_TYPE):
today = datetime.now(timezone.utc).date()

```
# Yıl verilmişse o yılın Ramazanına, verilmemişse en yakın Ramazana bak
if context.args:
    try:
        year = parse_year(context.args)
    except ValueError as e:
        return await reply_error(update, str(e))
else:
    year = today.year

# Önce bu yıl, sonra gelecek yıl
for y in [year, year + 1]:
    m, _ = find_month_date(y, 8)
    if m and m >= today:
        fark = (m - today).days
        if fark == 0:
            text = "🌙 *Bugün Ramazan başlıyor!* Hayırlı Ramazanlar! 🎊"
        elif fark == 1:
            text = f"🌙 *Yarın Ramazan başlıyor!*\n▸ Başlangıç: `{m}`"
        else:
            text = (
                f"🌙 *Ramazana Geri Sayım*\n\n"
                f"▸ Ramazan Başlangıcı : `{m}`\n"
                f"▸ Kalan              : *{fark} gün*"
            )
        return await update.message.reply_text(text, parse_mode="Markdown")

await reply_error(update, "Ramazan tarihi hesaplanamadı.")
```

# ══════════════════════════════════════════════

# KOMUT: /hilal

# ══════════════════════════════════════════════

async def hilal(update: Update, context: ContextTypes.DEFAULT_TYPE):
today = datetime.now(timezone.utc).date()

```
# En yakın yeni ayı bul (bugünden önceki son yeni ay)
nm = None
for t in reversed(NEW_MOONS):
    if t.date() <= today:
        nm = t
        break

if not nm:
    return await reply_error(update, "Yeni ay verisi bulunamadı.")

age_hours = (today - nm.date()).days * 24
score     = hilal_score(today, nm)

if score >= 18:
    durum  = "✅ Görünür — Hilal görülmesi kuvvetle muhtemel"
    emoji  = "🌙"
elif score >= 10:
    durum  = "🟡 Belirsiz — Koşullara bağlı, gözlem önerilir"
    emoji  = "🌛"
else:
    durum  = "❌ Görünmez — Hilal görülmesi zor"
    emoji  = "🌑"

text = (
    f"{emoji} *Hilal Durumu — {today}*\n\n"
    f"▸ Son Yeni Ay : `{nm.date()}`\n"
    f"▸ Ay Yaşı    : `{age_hours:.0f} saat`\n"
    f"▸ Görünürlük Skoru : `{score:.1f}`\n\n"
    f"📊 Durum: {durum}"
)
await update.message.reply_text(text, parse_mode="Markdown")
```

# ══════════════════════════════════════════════

# KOMUT: /miladiden YYYY-MM-DD

# ══════════════════════════════════════════════

async def miladiden(update: Update, context: ContextTypes.DEFAULT_TYPE):
try:
tarih = parse_date_arg(context.args)
except ValueError as e:
return await reply_error(update, str(e))

```
gun, ay_adi, ay_idx, hicri_yil = get_hijri(tarih)

if gun == 0:
    return await reply_error(update, "Bu tarih için Hicri karşılık hesaplanamadı.")

ozel = OZEL_GUNLER.get((ay_idx, gun), "")
ozel_line = f"\n🔔 *{ozel}*" if ozel else ""

text = (
    f"🔄 *Miladi → Hicri Çeviri*\n\n"
    f"▸ Miladi : `{tarih}`\n"
    f"▸ Hicri  : `{gun} {ay_adi} {hicri_yil}`"
    f"{ozel_line}"
)
await update.message.reply_text(text, parse_mode="Markdown")
```

# ══════════════════════════════════════════════

# KOMUT: /hicridenmiladi <gun> <AyAdı> <HicriYıl>

# Örnek: /hicridenmiladi 15 Ramazan 1446

# ══════════════════════════════════════════════

async def hicridenmiladi(update: Update, context: ContextTypes.DEFAULT_TYPE):
if len(context.args) < 3:
return await reply_error(
update,
“Kullanım: /hicridenmiladi <gün> <AyAdı> <HicriYıl>\n”
“Örnek: /hicridenmiladi 15 Ramazan 1446”
)

```
try:
    gun       = int(context.args[0])
    ay_adi    = context.args[1].capitalize()
    hicri_yil = int(context.args[2])
except ValueError:
    return await reply_error(update, "Gün ve yıl sayı olmalı. Örnek: /hicridenmiladi 15 Ramazan 1446")

if ay_adi not in AYLAR:
    return await reply_error(
        update,
        f"'{ay_adi}' geçerli bir Hicri ay adı değil.\nGeçerli aylar: {', '.join(AYLAR)}"
    )

if not (1 <= gun <= 30):
    return await reply_error(update, "Gün 1–30 arasında olmalı.")

ay_idx = AYLAR.index(ay_adi)
miladi = date_from_hijri(hicri_yil, ay_idx, gun)

if not miladi:
    return await reply_error(update, "Bu Hicri tarih için miladi karşılık hesap aralığı dışında.")

ozel = OZEL_GUNLER.get((ay_idx, gun), "")
ozel_line = f"\n🔔 *{ozel}*" if ozel else ""

text = (
    f"🔄 *Hicri → Miladi Çeviri*\n\n"
    f"▸ Hicri  : `{gun} {ay_adi} {hicri_yil}`\n"
    f"▸ Miladi : `{miladi}`"
    f"{ozel_line}"
)
await update.message.reply_text(text, parse_mode="Markdown")
```

# ══════════════════════════════════════════════

# KOMUT: /analiz

# ══════════════════════════════════════════════

async def analiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
await update.message.reply_text(“⏳ Analiz hesaplanıyor, lütfen bekleyin…”)

```
lines  = ["📊 *Ramazan Doğruluk Analizi (1995–2025)*\n"]
correct = 0
total   = 0
diffs   = []

for year, real in sorted(REAL_RAMADAN.items()):
    m, _ = find_month_date(year, 8)
    if not m:
        continue

    diff = (m - real).days
    diffs.append(diff)
    emoji = "✅" if abs(diff) <= 1 else ("🟡" if abs(diff) == 2 else "❌")

    lines.append(f"{emoji} `{year}` Hesap:`{m}` Gerçek:`{real}` Fark:`{diff:+d}`")

    if abs(diff) <= 1:
        correct += 1
    total += 1

acc       = (correct / total) * 100 if total else 0
ort_fark  = sum(abs(d) for d in diffs) / len(diffs) if diffs else 0
maks_fark = max(abs(d) for d in diffs) if diffs else 0

lines.append(
    f"\n📈 *Özet*\n"
    f"▸ Doğruluk (±1 gün) : *%{acc:.1f}*\n"
    f"▸ Ort. Sapma        : `{ort_fark:.2f} gün`\n"
    f"▸ Maks. Sapma       : `{maks_fark} gün`\n"
    f"▸ Toplam Test       : `{total}`"
)

# Telegram 4096 karakter sınırı
msg = "\n".join(lines)
if len(msg) > 4000:
    for chunk in [msg[i:i+4000] for i in range(0, len(msg), 4000)]:
        await update.message.reply_text(chunk, parse_mode="Markdown")
else:
    await update.message.reply_text(msg, parse_mode="Markdown")
```

# ══════════════════════════════════════════════

# KOMUT: /karsilastir <yil>

# ══════════════════════════════════════════════

async def karsilastir(update: Update, context: ContextTypes.DEFAULT_TYPE):
try:
year = parse_year(context.args)
except ValueError as e:
return await reply_error(update, str(e))

```
m_hesap, _ = find_month_date(year, 8)
m_real      = REAL_RAMADAN.get(year)

lines = [f"🔍 *{year} Ramazan Karşılaştırması*\n"]
lines.append(f"▸ Bu Bot (Astronomik) : `{m_hesap}`")

if m_real:
    diff = (m_hesap - m_real).days if m_hesap else "?"
    lines.append(f"▸ Gerçek/Referans     : `{m_real}` (Fark: `{diff:+d} gün`)")
else:
    lines.append(f"▸ Gerçek/Referans     : Veri yok")

# Diyanet yaklaşımı: genellikle hesap takvimi ±1
lines.append(
    f"\n📌 *Not:* Diyanet İşleri resmi takvimi ile fark "
    f"genellikle 0–2 gün arasında olup bölgesel hilal gözlemine göre değişir."
)

await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
```

# ══════════════════════════════════════════════

# KOMUT: /yardim

# ══════════════════════════════════════════════

async def yardim(update: Update, context: ContextTypes.DEFAULT_TYPE):
await start(update, context)

# ══════════════════════════════════════════════

# GLOBAL ERROR HANDLER

# ══════════════════════════════════════════════

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
logger.error(f”Hata: {context.error}”, exc_info=True)
if isinstance(update, Update) and update.message:
await update.message.reply_text(
“⚠️ Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin.\n”
“Sorun devam ederse /yardim yazarak komut listesini kontrol edin.”
)

# ══════════════════════════════════════════════

# BİLİNMEYEN KOMUT

# ══════════════════════════════════════════════

async def bilinmeyen(update: Update, context: ContextTypes.DEFAULT_TYPE):
await update.message.reply_text(
“❓ Bilinmeyen komut. /yardim yazarak tüm komutları görebilirsiniz.”
)

# ══════════════════════════════════════════════

# UYGULAMA

# ══════════════════════════════════════════════

def main():
app = ApplicationBuilder().token(TOKEN).build()

```
# Komutlar
app.add_handler(CommandHandler("start",           start))
app.add_handler(CommandHandler("yardim",          yardim))
app.add_handler(CommandHandler("bugun",           bugun))
app.add_handler(CommandHandler("yil",             yil))
app.add_handler(CommandHandler("ramazan",         ramazan))
app.add_handler(CommandHandler("arefe",           arefe))
app.add_handler(CommandHandler("bayramlar",       bayramlar))
app.add_handler(CommandHandler("kacgun",          kacgun))
app.add_handler(CommandHandler("hilal",           hilal))
app.add_handler(CommandHandler("miladiden",       miladiden))
app.add_handler(CommandHandler("hicridenmiladi",  hicridenmiladi))
app.add_handler(CommandHandler("analiz",          analiz))
app.add_handler(CommandHandler("karsilastir",     karsilastir))

# Bilinmeyen komutlar
app.add_handler(MessageHandler(filters.COMMAND, bilinmeyen))

# Hata yakalayıcı
app.add_error_handler(error_handler)

logger.info("🚀 Hicri Takvim Botu — Zirve Sürüm aktif!")
print("🚀 Hicri Takvim Botu — Zirve Sürüm aktif!")
app.run_polling()
```

if **name** == “**main**”:
main()
