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
raise EnvironmentError(“TOKEN ortam degiskeni tanimli degil!”)

# ══════════════════════════════════════════════

# SKYFIELD

# ══════════════════════════════════════════════

ts = load.timescale()

try:
eph = load(‘de421.bsp’)
logger.info(“de421.bsp yuklendi.”)
except Exception:
logger.info(“de421.bsp indiriliyor…”)
from skyfield.api import Loader
sky_load = Loader(’.’)
eph = sky_load(‘de421.bsp’)
logger.info(“de421.bsp indirildi ve yuklendi.”)

earth = eph[‘earth’]
moon  = eph[‘moon’]
sun   = eph[‘sun’]

# ══════════════════════════════════════════════

# KONUMLAR

# ══════════════════════════════════════════════

LOCATIONS = {
“Mekke”:    wgs84.latlon(21.4225, 39.8262),
“Ankara”:   wgs84.latlon(39.9334, 32.8597),
“Tahran”:   wgs84.latlon(35.6892, 51.3890),
“Kahire”:   wgs84.latlon(30.0444, 31.2357),
“Istanbul”: wgs84.latlon(41.0082, 28.9784),
}

# ══════════════════════════════════════════════

# YENI AYLAR

# ══════════════════════════════════════════════

def get_new_moons(start=1993, end=2037):
t0 = ts.utc(start, 1, 1)
t1 = ts.utc(end, 12, 31)
times, phases = find_discrete(t0, t1, moon_phases(eph))
return [
t.utc_datetime().replace(tzinfo=timezone.utc)
for t, p in zip(times, phases)
if p == 0
]

NEW_MOONS = get_new_moons()
logger.info(”%d yeni ay hesaplandi.”, len(NEW_MOONS))

# ══════════════════════════════════════════════

# GUNES BATISI

# ══════════════════════════════════════════════

def get_sunset(loc, year, month, day):
try:
t0 = ts.utc(year, month, day, 12)
t1 = ts.utc(year, month, day, 23, 59)
f  = sunrise_sunset(eph, loc)
times, events = find_discrete(t0, t1, f)
for t, e in zip(times, events):
if e == 0:
return t.utc_datetime().hour + t.utc_datetime().minute / 60.0
return 18.0
except Exception:
return 18.0

# ══════════════════════════════════════════════

# HILAL SKORU

# ══════════════════════════════════════════════

def hilal_score(check_date, nm):
total = 0.0
count = 0

```
for loc_name, loc in LOCATIONS.items():
    sunset_hour = get_sunset(loc, check_date.year, check_date.month, check_date.day)

    for minute_offset in range(30, 150, 15):
        hour_frac = sunset_hour + minute_offset / 60.0
        hour      = int(hour_frac)
        minute    = int((hour_frac - hour) * 60)

        if hour >= 24:
            break

        t = ts.utc(check_date.year, check_date.month, check_date.day, hour, minute)

        obs   = (earth + loc).at(t)
        m_app = obs.observe(moon).apparent()
        s_app = obs.observe(sun).apparent()

        alt_m, _, _ = m_app.altaz()
        elong       = m_app.separation_from(s_app).degrees
        alt_deg     = alt_m.degrees

        if alt_deg <= 0:
            continue

        age_hours = (
            datetime.combine(check_date, datetime.min.time(), tzinfo=timezone.utc) - nm
        ).total_seconds() / 3600.0

        illum = ((1 - math.cos(math.radians(elong))) / 2) * 100

        score = (
            alt_deg   * 1.5 +
            elong     * 0.8 +
            age_hours * 0.05 +
            illum     * 0.3
        )

        total += score
        count += 1

return total / count if count > 0 else 0.0
```

# ══════════════════════════════════════════════

# AY BASI KARARI

# ══════════════════════════════════════════════

def find_month_start(nm):
d1 = nm.date() + timedelta(days=1)
d2 = nm.date() + timedelta(days=2)

```
s1 = hilal_score(d1, nm)
s2 = hilal_score(d2, nm)

if s1 >= 18.0:
    return d1

if s1 > 0 and (s2 - s1) / max(s1, 1) > 0.25:
    return d2

return d1
```

# ══════════════════════════════════════════════

# TAKVIM

# ══════════════════════════════════════════════

logger.info(“Ay baslari hesaplaniyor…”)
MONTHS = sorted([find_month_start(nm) for nm in NEW_MOONS])
logger.info(”%d ay basi hesaplandi.”, len(MONTHS))

# ══════════════════════════════════════════════

# HICRI AY ISIMLERI

# ══════════════════════════════════════════════

AYLAR = [
“Muharrem”, “Safer”, “Rebiulevvel”, “Rebiulahir”,
“Cemaziyelevvel”, “Cemaziyelahir”, “Recep”,
“Saban”, “Ramazan”, “Sevval”, “Zilkade”, “Zilhicce”
]

# UTF-8 display versiyonu (Telegram mesajlarinda kullanilir)

AYLAR_TR = [
“Muharrem”, “Safer”, “Rebi\u00fclevvel”, “Rebi\u00fclahir”,
“Cemaziyelevvel”, “Cemaziyelahir”, “Recep”,
“\u015eaban”, “Ramazan”, “\u015eevval”, “Zilkade”, “Zilhicce”
]

OZEL_GUNLER = {
(0, 10):  “Asure Gunu”,
(1, 12):  “Mevlid Kandili”,
(6, 27):  “Mirac Kandili”,
(7, 15):  “Berat Kandili”,
(8,  1):  “Ramazan Baslangici”,
(8, 27):  “Kadir Gecesi (yaklasik)”,
(9,  1):  “Ramazan Bayrami 1. Gunu”,
(9,  2):  “Ramazan Bayrami 2. Gunu”,
(9,  3):  “Ramazan Bayrami 3. Gunu”,
(11, 9):  “Arefe Gunu”,
(11,10):  “Kurban Bayrami 1. Gunu”,
(11,11):  “Kurban Bayrami 2. Gunu”,
(11,12):  “Kurban Bayrami 3. Gunu”,
(11,13):  “Kurban Bayrami 4. Gunu”,
}

# ══════════════════════════════════════════════

# ANCHOR  – 1 Ramazan 1446 = 1 Mart 2025

# ══════════════════════════════════════════════

ANCHOR_TARGET = datetime(2025, 3, 1).date()
ANCHOR_INDEX  = min(
range(len(MONTHS)),
key=lambda i: abs((MONTHS[i] - ANCHOR_TARGET).days)
)
logger.info(“Anchor: MONTHS[%d] = %s”, ANCHOR_INDEX, MONTHS[ANCHOR_INDEX])

# ══════════════════════════════════════════════

# HICRI HESAP

# ══════════════════════════════════════════════

def get_hijri(check_date):
current = None
for i, m in enumerate(MONTHS):
if m <= check_date:
current = (m, i)

```
if not current:
    return 0, "?", -1, 0

start, idx = current
gun        = (check_date - start).days + 1
ay_index   = (idx - ANCHOR_INDEX) % 12
hicri_yil  = 1446 + (idx - ANCHOR_INDEX) // 12

return gun, AYLAR_TR[ay_index], ay_index, hicri_yil
```

def date_from_hijri(hicri_yil, ay_index, gun):
offset     = (hicri_yil - 1446) * 12 + (ay_index - 8)
target_idx = ANCHOR_INDEX + offset

```
if target_idx < 0 or target_idx >= len(MONTHS):
    return None

return MONTHS[target_idx] + timedelta(days=gun - 1)
```

def find_month_date(year_miladi, ay_index):
for i, m in enumerate(MONTHS):
idx = (i - ANCHOR_INDEX) % 12
if idx == ay_index and m.year == year_miladi:
return m, i
for i, m in enumerate(MONTHS):
idx = (i - ANCHOR_INDEX) % 12
if idx == ay_index and abs(m.year - year_miladi) == 1:
return m, i
return None, None

# ══════════════════════════════════════════════

# REFERANS VERISI

# ══════════════════════════════════════════════

REAL_RAMADAN = {
1995: date(1995, 2, 1),   1996: date(1996, 1, 22),
1997: date(1997, 1, 11),  1998: date(1998, 12, 20),
1999: date(1999, 12, 9),  2000: date(2000, 11, 27),
2001: date(2001, 11, 16), 2002: date(2002, 11, 6),
2003: date(2003, 10, 27), 2004: date(2004, 10, 15),
2005: date(2005, 10, 4),  2006: date(2006, 9, 24),
2007: date(2007, 9, 13),  2008: date(2008, 9, 1),
2009: date(2009, 8, 22),  2010: date(2010, 8, 11),
2011: date(2011, 8, 1),   2012: date(2012, 7, 20),
2013: date(2013, 7, 9),   2014: date(2014, 6, 28),
2015: date(2015, 6, 18),  2016: date(2016, 6, 6),
2017: date(2017, 5, 27),  2018: date(2018, 5, 16),
2019: date(2019, 5, 6),   2020: date(2020, 4, 24),
2021: date(2021, 4, 13),  2022: date(2022, 4, 2),
2023: date(2023, 3, 23),  2024: date(2024, 3, 11),
2025: date(2025, 3, 1),
}

# ══════════════════════════════════════════════

# YARDIMCI

# ══════════════════════════════════════════════

def parse_year(args, min_y=1995, max_y=2037):
if not args:
raise ValueError(“Lutfen bir yil girin. Ornek: /ramazan 2027”)
try:
y = int(args[0])
except ValueError:
raise ValueError(”’{}’ gecerli bir yil degil.”.format(args[0]))
if not (min_y <= y <= max_y):
raise ValueError(“Yil {}-{} arasinda olmali.”.format(min_y, max_y))
return y

def parse_date_arg(args):
if not args:
raise ValueError(“Lutfen tarih girin. Ornek: /miladiden 2026-03-20”)
try:
return datetime.strptime(args[0], “%Y-%m-%d”).date()
except ValueError:
raise ValueError(“Tarih formati YYYY-AA-GG olmali. Ornek: 2026-03-20”)

async def reply_error(update, msg):
await update.message.reply_text(“Hata: {}”.format(msg))

# ══════════════════════════════════════════════

# /start & /yardim

# ══════════════════════════════════════════════

HELP_TEXT = (
“HİCRİ TAKVİM BOTU\n\n”
“/bugun                           Bugunun Hicri tarihi\n”
“/yil 2027                        Yil bazli Hicri takvim\n”
“/ramazan 2027                    Ramazan baslangici\n”
“/arefe 2027                      Arefe ve Kurban Bayrami\n”
“/bayramlar 2027                  Tum dini gunler\n”
“/kacgun                          Ramazana kac gun kaldi\n”
“/kacgun 2028                     Belirli yil Ramazanina\n”
“/hilal                           Bugun hilal gorunur mu?\n”
“/miladiden 2026-03-20            Miladi > Hicri\n”
“/hicridenmiladi 15 Ramazan 1446  Hicri > Miladi\n”
“/analiz                          Dogruluk analizi\n”
“/karsilastir 2026                Bot vs gercek veri\n”
“/yardim                          Bu menu\n”
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
await update.message.reply_text(HELP_TEXT)

async def yardim(update: Update, context: ContextTypes.DEFAULT_TYPE):
await update.message.reply_text(HELP_TEXT)

# ══════════════════════════════════════════════

# /bugun

# ══════════════════════════════════════════════

async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
today = datetime.now(timezone.utc).date()
gun, ay_adi, ay_idx, hicri_yil = get_hijri(today)

```
ozel = OZEL_GUNLER.get((ay_idx, gun), "")
text = "Bugun: {}\nHicri: {} {} {}".format(today, gun, ay_adi, hicri_yil)
if ozel:
    text += "\n>>> {}".format(ozel)

await update.message.reply_text(text)
```

# ══════════════════════════════════════════════

# /yil

# ══════════════════════════════════════════════

async def yil(update: Update, context: ContextTypes.DEFAULT_TYPE):
try:
year = parse_year(context.args)
except ValueError as e:
return await reply_error(update, str(e))

```
lines = ["{} Yili Hicri Ay Baslari\n".format(year)]
found = False

for i, m in enumerate(MONTHS):
    if m.year == year:
        idx  = (i - ANCHOR_INDEX) % 12
        hyil = 1446 + (i - ANCHOR_INDEX) // 12
        lines.append("{} {}: {}".format(AYLAR_TR[idx], hyil, m))
        found = True

if not found:
    lines.append("Bu yil icin veri bulunamadi.")

await update.message.reply_text("\n".join(lines))
```

# ══════════════════════════════════════════════

# /ramazan

# ══════════════════════════════════════════════

async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
try:
year = parse_year(context.args)
except ValueError as e:
return await reply_error(update, str(e))

```
m, _ = find_month_date(year, 8)
if m:
    text = (
        "Ramazan {}\n"
        "Baslangic          : {}\n"
        "Bitis (29. gun)    : {}\n"
        "Kadir Gecesi (~27) : {}"
    ).format(year, m, m + timedelta(days=28), m + timedelta(days=26))
else:
    text = "{} icin Ramazan verisi bulunamadi.".format(year)

await update.message.reply_text(text)
```

# ══════════════════════════════════════════════

# /arefe

# ══════════════════════════════════════════════

async def arefe(update: Update, context: ContextTypes.DEFAULT_TYPE):
try:
year = parse_year(context.args)
except ValueError as e:
return await reply_error(update, str(e))

```
m, _ = find_month_date(year, 11)
if m:
    text = (
        "Kurban Bayrami {}\n"
        "Arefe    : {}\n"
        "Bayram 1 : {}\n"
        "Bayram 2 : {}\n"
        "Bayram 3 : {}\n"
        "Bayram 4 : {}"
    ).format(
        year,
        m + timedelta(days=8),
        m + timedelta(days=9),
        m + timedelta(days=10),
        m + timedelta(days=11),
        m + timedelta(days=12),
    )
else:
    text = "{} icin Zilhicce verisi bulunamadi.".format(year)

await update.message.reply_text(text)
```

# ══════════════════════════════════════════════

# /bayramlar

# ══════════════════════════════════════════════

async def bayramlar(update: Update, context: ContextTypes.DEFAULT_TYPE):
try:
year = parse_year(context.args)
except ValueError as e:
return await reply_error(update, str(e))

```
LISTE = [
    (0, 10,  "Asure Gunu"),
    (1, 12,  "Mevlid Kandili"),
    (6, 27,  "Mirac Kandili"),
    (7, 15,  "Berat Kandili"),
    (8,  1,  "Ramazan Baslangici"),
    (8, 27,  "Kadir Gecesi (~)"),
    (9,  1,  "Ramazan Bayrami 1. Gun"),
    (9,  2,  "Ramazan Bayrami 2. Gun"),
    (9,  3,  "Ramazan Bayrami 3. Gun"),
    (11, 9,  "Arefe Gunu"),
    (11,10,  "Kurban Bayrami 1. Gun"),
    (11,11,  "Kurban Bayrami 2. Gun"),
    (11,12,  "Kurban Bayrami 3. Gun"),
    (11,13,  "Kurban Bayrami 4. Gun"),
]

lines = ["{} Dini Gunler Takvimi\n".format(year)]
found = False

for ay_idx, gun, isim in LISTE:
    m, _ = find_month_date(year, ay_idx)
    if m:
        hedef = m + timedelta(days=gun - 1)
        if abs(hedef.year - year) <= 1:
            lines.append("{} - {}".format(hedef, isim))
            found = True

if not found:
    lines.append("Bu yil icin veri bulunamadi.")

await update.message.reply_text("\n".join(lines))
```

# ══════════════════════════════════════════════

# /kacgun

# ══════════════════════════════════════════════

async def kacgun(update: Update, context: ContextTypes.DEFAULT_TYPE):
today = datetime.now(timezone.utc).date()

```
if context.args:
    try:
        year = parse_year(context.args)
    except ValueError as e:
        return await reply_error(update, str(e))
    years_to_check = [year]
else:
    years_to_check = [today.year, today.year + 1]

for y in years_to_check:
    m, _ = find_month_date(y, 8)
    if m and m >= today:
        fark = (m - today).days
        if fark == 0:
            text = "Bugun Ramazan basliyor! Hayirli Ramazanlar!"
        elif fark == 1:
            text = "Yarin Ramazan basliyor!\nBaslangic: {}".format(m)
        else:
            text = "Ramazana Geri Sayim\nBaslangic : {}\nKalan     : {} gun".format(m, fark)
        return await update.message.reply_text(text)

await reply_error(update, "Ramazan tarihi hesaplanamadi.")
```

# ══════════════════════════════════════════════

# /hilal

# ══════════════════════════════════════════════

async def hilal(update: Update, context: ContextTypes.DEFAULT_TYPE):
today = datetime.now(timezone.utc).date()

```
nm = None
for t in reversed(NEW_MOONS):
    if t.date() <= today:
        nm = t
        break

if not nm:
    return await reply_error(update, "Yeni ay verisi bulunamadi.")

age_hours = (today - nm.date()).days * 24
score     = hilal_score(today, nm)

if score >= 18:
    durum = "Gorunur - Hilal gorulmesi kuvvetle muhtemel"
elif score >= 10:
    durum = "Belirsiz - Kosullara bagli, gozlem onerilir"
else:
    durum = "Gorunmez - Hilal gorulmesi zor"

text = (
    "Hilal Durumu - {}\n\n"
    "Son Yeni Ay      : {}\n"
    "Ay Yasi          : {:.0f} saat\n"
    "Gorunurluk Skoru : {:.1f}\n\n"
    "Durum: {}"
).format(today, nm.date(), age_hours, score, durum)

await update.message.reply_text(text)
```

# ══════════════════════════════════════════════

# /miladiden

# ══════════════════════════════════════════════

async def miladiden(update: Update, context: ContextTypes.DEFAULT_TYPE):
try:
tarih = parse_date_arg(context.args)
except ValueError as e:
return await reply_error(update, str(e))

```
gun, ay_adi, ay_idx, hicri_yil = get_hijri(tarih)

if gun == 0:
    return await reply_error(update, "Bu tarih icin Hicri karsilik hesaplanamadi.")

ozel = OZEL_GUNLER.get((ay_idx, gun), "")
text = "Miladi > Hicri\n\nMiladi : {}\nHicri  : {} {} {}".format(
    tarih, gun, ay_adi, hicri_yil
)
if ozel:
    text += "\n>>> {}".format(ozel)

await update.message.reply_text(text)
```

# ══════════════════════════════════════════════

# /hicridenmiladi

# ══════════════════════════════════════════════

async def hicridenmiladi(update: Update, context: ContextTypes.DEFAULT_TYPE):
if len(context.args) < 3:
return await reply_error(
update,
“Kullanim: /hicridenmiladi <gun> <AyAdi> <HicriYil>\n”
“Ornek: /hicridenmiladi 15 Ramazan 1446”
)

```
try:
    gun       = int(context.args[0])
    ay_adi    = context.args[1].strip()
    hicri_yil = int(context.args[2])
except ValueError:
    return await reply_error(update, "Gun ve yil sayi olmali.")

ay_idx = None
for i in range(len(AYLAR)):
    if (AYLAR[i].lower() == ay_adi.lower() or
            AYLAR_TR[i].lower() == ay_adi.lower()):
        ay_idx = i
        break

if ay_idx is None:
    return await reply_error(
        update,
        "'{}' gecerli bir Hicri ay adi degil.\n"
        "Gecerli aylar: {}".format(ay_adi, ", ".join(AYLAR_TR))
    )

if not (1 <= gun <= 30):
    return await reply_error(update, "Gun 1-30 arasinda olmali.")

miladi = date_from_hijri(hicri_yil, ay_idx, gun)

if not miladi:
    return await reply_error(update, "Bu Hicri tarih hesap araliginin disinda.")

ozel = OZEL_GUNLER.get((ay_idx, gun), "")
text = "Hicri > Miladi\n\nHicri  : {} {} {}\nMiladi : {}".format(
    gun, AYLAR_TR[ay_idx], hicri_yil, miladi
)
if ozel:
    text += "\n>>> {}".format(ozel)

await update.message.reply_text(text)
```

# ══════════════════════════════════════════════

# /analiz

# ══════════════════════════════════════════════

async def analiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
await update.message.reply_text(“Analiz hesaplaniyor, lutfen bekleyin…”)

```
lines   = ["Ramazan Dogruluk Analizi (1995-2025)\n"]
correct = 0
total   = 0
diffs   = []

for year, real in sorted(REAL_RAMADAN.items()):
    m, _ = find_month_date(year, 8)
    if not m:
        continue

    diff = (m - real).days
    diffs.append(diff)

    if abs(diff) <= 1:
        tag = "[OK]"
        correct += 1
    elif abs(diff) == 2:
        tag = "[~] "
    else:
        tag = "[X] "

    lines.append("{} {} Hesap:{} Gercek:{} Fark:{:+d}".format(
        tag, year, m, real, diff
    ))
    total += 1

acc  = (correct / total) * 100 if total else 0
ort  = sum(abs(d) for d in diffs) / len(diffs) if diffs else 0
maks = max(abs(d) for d in diffs) if diffs else 0

lines.append(
    "\nOzet\n"
    "Dogruluk (+-1 gun) : %{:.1f}\n"
    "Ort. Sapma         : {:.2f} gun\n"
    "Maks. Sapma        : {} gun\n"
    "Toplam Test        : {}".format(acc, ort, maks, total)
)

msg = "\n".join(lines)
for chunk in [msg[i:i+4000] for i in range(0, len(msg), 4000)]:
    await update.message.reply_text(chunk)
```

# ══════════════════════════════════════════════

# /karsilastir

# ══════════════════════════════════════════════

async def karsilastir(update: Update, context: ContextTypes.DEFAULT_TYPE):
try:
year = parse_year(context.args)
except ValueError as e:
return await reply_error(update, str(e))

```
m_hesap, _ = find_month_date(year, 8)
m_real     = REAL_RAMADAN.get(year)

lines = ["{} Ramazan Karsilastirmasi\n".format(year)]
lines.append("Bu Bot (Astronomik) : {}".format(m_hesap))

if m_real and m_hesap:
    diff = (m_hesap - m_real).days
    lines.append("Gercek / Referans   : {} (Fark: {:+d} gun)".format(m_real, diff))
elif m_real:
    lines.append("Gercek / Referans   : {}".format(m_real))
else:
    lines.append("Gercek / Referans   : Veri yok")

lines.append(
    "\nNot: Diyanet takvimi ile fark genellikle 0-2 gun "
    "arasinda olup bolgesel hilal gozlemine gore degisir."
)

await update.message.reply_text("\n".join(lines))
```

# ══════════════════════════════════════════════

# HATA YONETIMI

# ══════════════════════════════════════════════

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
logger.error(“Hata: %s”, context.error, exc_info=True)
if isinstance(update, Update) and update.message:
await update.message.reply_text(
“Beklenmeyen bir hata olustu. Lutfen tekrar deneyin.\n”
“/yardim yazarak komut listesini gorebilirsiniz.”
)

async def bilinmeyen(update: Update, context: ContextTypes.DEFAULT_TYPE):
await update.message.reply_text(
“Bilinmeyen komut. /yardim yazarak tum komutlari gorebilirsiniz.”
)

# ══════════════════════════════════════════════

# MAIN

# ══════════════════════════════════════════════

def main():
app = ApplicationBuilder().token(TOKEN).build()

```
app.add_handler(CommandHandler("start",          start))
app.add_handler(CommandHandler("yardim",         yardim))
app.add_handler(CommandHandler("bugun",          bugun))
app.add_handler(CommandHandler("yil",            yil))
app.add_handler(CommandHandler("ramazan",        ramazan))
app.add_handler(CommandHandler("arefe",          arefe))
app.add_handler(CommandHandler("bayramlar",      bayramlar))
app.add_handler(CommandHandler("kacgun",         kacgun))
app.add_handler(CommandHandler("hilal",          hilal))
app.add_handler(CommandHandler("miladiden",      miladiden))
app.add_handler(CommandHandler("hicridenmiladi", hicridenmiladi))
app.add_handler(CommandHandler("analiz",         analiz))
app.add_handler(CommandHandler("karsilastir",    karsilastir))
app.add_handler(MessageHandler(filters.COMMAND,  bilinmeyen))

app.add_error_handler(error_handler)

logger.info("Hicri Takvim Botu aktif!")
print("Hicri Takvim Botu aktif!")
app.run_polling()
```

if **name** == “**main**”:
main()
