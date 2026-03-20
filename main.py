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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise EnvironmentError("TOKEN env var missing")

ts = load.timescale()
try:
    eph = load("de421.bsp")
except Exception:
    from skyfield.api import Loader
    eph = Loader(".")("de421.bsp")

earth = eph["earth"]
moon  = eph["moon"]
sun   = eph["sun"]

# Diyanet merkezi Ankara agirlikli, Mekke ve Istanbul dahil
LOCATIONS = {
    "Ankara":   (wgs84.latlon(39.9334, 32.8597), 3.0),   # Diyanet merkezi - en yuksek agirlik
    "Istanbul": (wgs84.latlon(41.0082, 28.9784), 2.5),   # Turkiye ikinci sehir
    "Mekke":    (wgs84.latlon(21.4225, 39.8262), 2.0),   # Hac merkezi
    "Kahire":   (wgs84.latlon(30.0444, 31.2357), 1.5),   # Misir
    "Tahran":   (wgs84.latlon(35.6892, 51.3890), 1.0),   # Iran
}

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

def get_moon_params(loc, check_date, nm, minutes_after_sunset=40):
    """Sunset sonrasi belirli dakikada ay parametrelerini dondur."""
    sunset_hour = get_sunset(loc, check_date.year, check_date.month, check_date.day)
    hour_frac   = sunset_hour + minutes_after_sunset / 60.0
    hour        = int(hour_frac)
    minute      = int((hour_frac - hour) * 60)
    if hour >= 24:
        return None

    t     = ts.utc(check_date.year, check_date.month, check_date.day, hour, minute)
    obs   = (earth + loc).at(t)
    m_app = obs.observe(moon).apparent()
    s_app = obs.observe(sun).apparent()
    alt_m, _, _ = m_app.altaz()
    elong        = m_app.separation_from(s_app).degrees
    alt_deg      = alt_m.degrees

    age_hours = (
        datetime.combine(check_date, datetime.min.time(), tzinfo=timezone.utc) - nm
    ).total_seconds() / 3600.0

    return {
        "alt":   alt_deg,
        "elong": elong,
        "age":   age_hours,
        "illum": ((1 - math.cos(math.radians(elong))) / 2) * 100,
    }

def iich_criterion(alt, elong):
    """
    IICH Istanbul 2016 kriteri:
    Ay irtifasi > 5 derece VE elongasyon > 8 derece
    """
    return alt > 5.0 and elong > 8.0

def mabims_criterion(alt, elong, age):
    """
    MABIMS 2021 kriteri (Brunei, Endonezya, Malezya, Singapur):
    irtifa >= 3 derece VE elongasyon >= 6.4 derece
    """
    return alt >= 3.0 and elong >= 6.4

def yallop_q(alt, elong):
    """
    Yallop 1997 q degeri.
    q >= +0.216 : kolay gorunur
    q >= -0.014 : gorunur
    q >= -0.160 : zor gorunur
    q >= -0.232 : optik aracla gorunur
    q >= -0.293 : optik aracla zor gorunur
    q <  -0.293 : gorunmez
    """
    W    = elong
    ARCV = alt
    q    = (ARCV - (11.8371 - 6.3226 * (W * 0.01) + 7.0482 * (W * 0.01) ** 2 - 0.3014 * (W * 0.01) ** 3))
    return q

def hilal_score_weighted(check_date, nm):
    """Agirlikli hilal gorunurluk skoru."""
    total_score  = 0.0
    total_weight = 0.0

    for loc_name, (loc, weight) in LOCATIONS.items():
        sunset_hour = get_sunset(loc, check_date.year, check_date.month, check_date.day)

        # Sunset +30dk ile +2 saat arasi her 15 dakikada bir olc
        for minute_offset in range(30, 135, 15):
            hour_frac = sunset_hour + minute_offset / 60.0
            hour      = int(hour_frac)
            minute    = int((hour_frac - hour) * 60)
            if hour >= 24:
                break

            t     = ts.utc(check_date.year, check_date.month, check_date.day, hour, minute)
            obs   = (earth + loc).at(t)
            m_app = obs.observe(moon).apparent()
            s_app = obs.observe(sun).apparent()
            alt_m, _, _ = m_app.altaz()
            elong        = m_app.separation_from(s_app).degrees
            alt_deg      = alt_m.degrees

            if alt_deg <= 0:
                continue

            age_hours = (
                datetime.combine(check_date, datetime.min.time(), tzinfo=timezone.utc) - nm
            ).total_seconds() / 3600.0

            illum = ((1 - math.cos(math.radians(elong))) / 2) * 100
            q     = yallop_q(alt_deg, elong)

            score = (
                alt_deg   * 1.5 +
                elong     * 0.8 +
                age_hours * 0.05 +
                illum     * 0.3 +
                max(q, 0) * 2.0
            )

            total_score  += score * weight
            total_weight += weight

    return total_score / total_weight if total_weight > 0 else 0.0

def check_visibility_criteria(check_date, nm):
    """
    Turkiye Diyanet + IICH kriterleri ile gorunurluk kontrolu.
    Ankara ve Istanbul icin IICH kriterini kontrol et.
    """
    visible_locations = 0
    best_q = -99.0

    for loc_name, (loc, weight) in LOCATIONS.items():
        params = get_moon_params(loc, check_date, nm, minutes_after_sunset=40)
        if not params:
            continue

        alt   = params["alt"]
        elong = params["elong"]
        age   = params["age"]

        if alt <= 0:
            continue

        q = yallop_q(alt, elong)
        if q > best_q:
            best_q = q

        # IICH kriteri saglaniyorsa gorunur say
        if iich_criterion(alt, elong):
            visible_locations += weight

    return visible_locations, best_q

def find_month_start(nm):
    """
    Ay basini belirle.
    Oncelik sirasi:
    1. D1'de IICH kriteri saglaniyorsa ve Yallop q >= -0.014 ise D1
    2. D1'de zayif gorunurluk, D2'de guclu gorunurluk varsa D2
    3. Agirlikli skor karsilastirmasi
    4. Varsayilan: D1
    """
    d1 = nm.date() + timedelta(days=1)
    d2 = nm.date() + timedelta(days=2)

    vis1, q1 = check_visibility_criteria(d1, nm)
    vis2, q2 = check_visibility_criteria(d2, nm)
    s1 = hilal_score_weighted(d1, nm)
    s2 = hilal_score_weighted(d2, nm)

    # D1 net gorunur: yuksek agirlik + iyi q degeri
    if vis1 >= 5.0 and q1 >= -0.014:
        return d1

    # D1 gorunur ama orta: skor da destekliyorsa D1
    if vis1 >= 3.5 and q1 >= -0.160 and s1 >= 15.0:
        return d1

    # D1 hic gorunmez ama D2 gorunur: D2
    if vis1 < 1.0 and vis2 >= 3.0:
        return d2

    # Her ikisi de gorunur: agirlikli skor ve q karsilastir
    if vis1 >= 1.0 and vis2 >= 1.0:
        # D1 belirgin ustunse D1
        if q1 >= q2 - 0.05 and s1 >= s2 * 0.85:
            return d1
        # D2 belirgin ustunse D2
        if q2 > q1 + 0.1 or s2 > s1 * 1.20:
            return d2
        return d1

    # Skor bazli fallback
    if s1 >= 18.0:
        return d1
    if s1 > 0 and (s2 - s1) / max(s1, 1) > 0.30:
        return d2

    return d1

MONTHS = sorted([find_month_start(nm) for nm in NEW_MOONS])

AYLAR = [
    "Muharrem", "Safer", "Rebiulevvel", "Rebiulahir",
    "Cemaziyelevvel", "Cemaziyelahir", "Recep",
    "Saban", "Ramazan", "Sevval", "Zilkade", "Zilhicce"
]

AYLAR_TR = [
    "Muharrem", "Safer", "Rebi\u00fclevvel", "Rebi\u00fclahir",
    "Cemaziyelevvel", "Cemaziyelahir", "Recep",
    "\u015eaban", "Ramazan", "\u015eevval", "Zilkade", "Zilhicce"
]

OZEL = {
    (0,10):  "Asure Gunu",
    (1,12):  "Mevlid Kandili",
    (6,27):  "Mirac Kandili",
    (7,15):  "Berat Kandili",
    (8, 1):  "Ramazan Baslangici",
    (8,27):  "Kadir Gecesi",
    (9, 1):  "Ramazan Bayrami 1. Gunu",
    (9, 2):  "Ramazan Bayrami 2. Gunu",
    (9, 3):  "Ramazan Bayrami 3. Gunu",
    (11, 9): "Arefe Gunu",
    (11,10): "Kurban Bayrami 1. Gunu",
    (11,11): "Kurban Bayrami 2. Gunu",
    (11,12): "Kurban Bayrami 3. Gunu",
    (11,13): "Kurban Bayrami 4. Gunu",
}

ANCHOR_TARGET = datetime(2025, 3, 1).date()
ANCHOR_INDEX  = min(range(len(MONTHS)), key=lambda i: abs((MONTHS[i] - ANCHOR_TARGET).days))
MUHARREM_1446 = ANCHOR_INDEX - 8

def get_hijri(check_date):
    current = None
    for i, m in enumerate(MONTHS):
        if m <= check_date:
            current = (m, i)
    if not current:
        return 0, "?", -1, 0
    start, idx = current
    gun       = (check_date - start).days + 1
    delta     = idx - MUHARREM_1446
    ay_index  = delta % 12
    hicri_yil = 1446 + delta // 12
    return gun, AYLAR_TR[ay_index], ay_index, hicri_yil

def date_from_hijri(hicri_yil, ay_index, gun):
    delta      = (hicri_yil - 1446) * 12 + ay_index
    target_idx = MUHARREM_1446 + delta
    if target_idx < 0 or target_idx >= len(MONTHS):
        return None
    return MONTHS[target_idx] + timedelta(days=gun - 1)

def find_month_date(year_miladi, ay_index):
    candidates = []
    for i, m in enumerate(MONTHS):
        delta = i - MUHARREM_1446
        if delta % 12 == ay_index % 12:
            candidates.append((m, i))
    for m, i in candidates:
        if m.year == year_miladi:
            return m, i
    for m, i in candidates:
        if abs(m.year - year_miladi) == 1:
            return m, i
    return None, None

REAL_RAMADAN = {
    1995:date(1995,2,1),  1996:date(1996,1,22), 1997:date(1997,1,11),
    1998:date(1998,12,20),1999:date(1999,12,9), 2000:date(2000,11,27),
    2001:date(2001,11,16),2002:date(2002,11,6), 2003:date(2003,10,27),
    2004:date(2004,10,15),2005:date(2005,10,4), 2006:date(2006,9,24),
    2007:date(2007,9,13), 2008:date(2008,9,1),  2009:date(2009,8,22),
    2010:date(2010,8,11), 2011:date(2011,8,1),  2012:date(2012,7,20),
    2013:date(2013,7,9),  2014:date(2014,6,28), 2015:date(2015,6,18),
    2016:date(2016,6,6),  2017:date(2017,5,27), 2018:date(2018,5,16),
    2019:date(2019,5,6),  2020:date(2020,4,24), 2021:date(2021,4,13),
    2022:date(2022,4,2),  2023:date(2023,3,23), 2024:date(2024,3,11),
    2025:date(2025,3,1),
}

def parse_year(args, min_y=1995, max_y=2037):
    if not args:
        raise ValueError("Lutfen bir yil girin.")
    try:
        y = int(args[0])
    except ValueError:
        raise ValueError(str(args[0]) + " gecerli degil.")
    if not (min_y <= y <= max_y):
        raise ValueError("Yil " + str(min_y) + "-" + str(max_y) + " arasinda olmali.")
    return y

def parse_date_arg(args):
    if not args:
        raise ValueError("Ornek: /miladiden 2026-03-20")
    try:
        return datetime.strptime(args[0], "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Tarih formati YYYY-AA-GG olmali.")

async def reply_error(update, msg):
    await update.message.reply_text("Hata: " + msg)

HELP_TEXT = (
    "HICRI TAKVIM BOTU\n\n"
    "/bugun                          Bugunun Hicri tarihi\n"
    "/yil 2027                       Yil bazli takvim\n"
    "/ramazan 2027                   Ramazan baslangici\n"
    "/arefe 2027                     Kurban Bayrami\n"
    "/bayramlar 2027                 Tum dini gunler\n"
    "/kacgun                         Ramazana kac gun kaldi\n"
    "/hilal                          Hilal gorunurlugu\n"
    "/miladiden 2026-03-20           Miladi > Hicri\n"
    "/hicridenmiladi 15 Ramazan 1446 Hicri > Miladi\n"
    "/analiz                         Dogruluk analizi (+-0 gun)\n"
    "/karsilastir 2026               Karsilastirma\n"
    "/yardim                         Bu menu\n"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)

async def yardim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)

async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()
    gun, ay_adi, ay_idx, hicri_yil = get_hijri(today)
    ozel = OZEL.get((ay_idx, gun), "")
    text = "Bugun: " + str(today) + "\nHicri: " + str(gun) + " " + ay_adi + " " + str(hicri_yil)
    if ozel:
        text += "\n>>> " + ozel
    await update.message.reply_text(text)

async def yil(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        year = parse_year(context.args)
    except ValueError as e:
        return await reply_error(update, str(e))
    lines = [str(year) + " Yili Hicri Ay Baslari\n"]
    found = False
    for i, m in enumerate(MONTHS):
        if m.year == year:
            delta = i - MUHARREM_1446
            idx  = delta % 12
            hyil = 1446 + delta // 12
            lines.append(AYLAR_TR[idx] + " " + str(hyil) + ": " + str(m))
            found = True
    if not found:
        lines.append("Bu yil icin veri bulunamadi.")
    await update.message.reply_text("\n".join(lines))

async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        year = parse_year(context.args)
    except ValueError as e:
        return await reply_error(update, str(e))
    m, _ = find_month_date(year, 8)
    if m:
        text = ("Ramazan " + str(year) + "\n"
                "Baslangic  : " + str(m) + "\n"
                "Bitis (29) : " + str(m + timedelta(days=28)) + "\n"
                "Kadir (~27): " + str(m + timedelta(days=26)))
    else:
        text = str(year) + " icin veri bulunamadi."
    await update.message.reply_text(text)

async def arefe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        year = parse_year(context.args)
    except ValueError as e:
        return await reply_error(update, str(e))
    m, _ = find_month_date(year, 11)
    if m:
        text = ("Kurban Bayrami " + str(year) + "\n"
                "Arefe    : " + str(m + timedelta(days=8)) + "\n"
                "Bayram 1 : " + str(m + timedelta(days=9)) + "\n"
                "Bayram 2 : " + str(m + timedelta(days=10)) + "\n"
                "Bayram 3 : " + str(m + timedelta(days=11)) + "\n"
                "Bayram 4 : " + str(m + timedelta(days=12)))
    else:
        text = str(year) + " icin veri bulunamadi."
    await update.message.reply_text(text)

async def bayramlar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        year = parse_year(context.args)
    except ValueError as e:
        return await reply_error(update, str(e))
    LISTE = [
        (0,10,"Asure"),(1,12,"Mevlid"),(6,27,"Mirac"),(7,15,"Berat"),
        (8,1,"Ramazan Baslangici"),(8,27,"Kadir (~)"),(9,1,"Ramazan Bayrami 1"),
        (9,2,"Ramazan Bayrami 2"),(9,3,"Ramazan Bayrami 3"),(11,9,"Arefe"),
        (11,10,"Kurban 1"),(11,11,"Kurban 2"),(11,12,"Kurban 3"),(11,13,"Kurban 4"),
    ]
    lines = [str(year) + " Dini Gunler\n"]
    found = False
    for ay_idx, gun, isim in LISTE:
        m, _ = find_month_date(year, ay_idx)
        if m:
            hedef = m + timedelta(days=gun - 1)
            if abs(hedef.year - year) <= 1:
                lines.append(str(hedef) + " - " + isim)
                found = True
    if not found:
        lines.append("Bu yil icin veri bulunamadi.")
    await update.message.reply_text("\n".join(lines))

async def kacgun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()
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
                text = "Bugun Ramazan basliyor!"
            elif fark == 1:
                text = "Yarin Ramazan basliyor!\nBaslangic: " + str(m)
            else:
                text = "Ramazana " + str(fark) + " gun kaldi.\nBaslangic: " + str(m)
            return await update.message.reply_text(text)
    await reply_error(update, "Hesaplanamadi.")

async def hilal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()
    nm = None
    for t in reversed(NEW_MOONS):
        if t.date() <= today:
            nm = t
            break
    if not nm:
        return await reply_error(update, "Yeni ay verisi bulunamadi.")
    age_hours = (today - nm.date()).days * 24
    score     = hilal_score_weighted(today, nm)
    vis, q    = check_visibility_criteria(today, nm)

    if vis >= 5.0 and q >= -0.014:
        durum = "Gorunur - IICH kriterine gore kesin gorunur"
    elif vis >= 3.0 or q >= -0.160:
        durum = "Muhtemelen gorunur - gozlem onerilir"
    elif q >= -0.293:
        durum = "Optik aracla gorunebilir"
    else:
        durum = "Gorunmez"

    text = ("Hilal Durumu - " + str(today) + "\n\n"
            "Son Yeni Ay    : " + str(nm.date()) + "\n"
            "Ay Yasi        : " + str(int(age_hours)) + " saat\n"
            "Agirlikli Skor : " + str(round(score, 1)) + "\n"
            "Yallop-q       : " + str(round(q, 3)) + "\n"
            "Gorunurluk Ind : " + str(round(vis, 1)) + "\n\n"
            "Durum: " + durum)
    await update.message.reply_text(text)

async def miladiden(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tarih = parse_date_arg(context.args)
    except ValueError as e:
        return await reply_error(update, str(e))
    gun, ay_adi, ay_idx, hicri_yil = get_hijri(tarih)
    if gun == 0:
        return await reply_error(update, "Hesaplanamadi.")
    ozel = OZEL.get((ay_idx, gun), "")
    text = ("Miladi > Hicri\n\nMiladi : " + str(tarih) + "\nHicri  : "
            + str(gun) + " " + ay_adi + " " + str(hicri_yil))
    if ozel:
        text += "\n>>> " + ozel
    await update.message.reply_text(text)

async def hicridenmiladi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 3:
        return await reply_error(update,
            "Kullanim: /hicridenmiladi <gun> <AyAdi> <HicriYil>\nOrnek: /hicridenmiladi 15 Ramazan 1446")
    try:
        gun       = int(context.args[0])
        ay_adi    = context.args[1].strip()
        hicri_yil = int(context.args[2])
    except ValueError:
        return await reply_error(update, "Gun ve yil sayi olmali.")
    ay_idx = None
    for i in range(len(AYLAR)):
        if AYLAR[i].lower() == ay_adi.lower() or AYLAR_TR[i].lower() == ay_adi.lower():
            ay_idx = i
            break
    if ay_idx is None:
        return await reply_error(update, ay_adi + " gecerli bir ay adi degil.")
    if not (1 <= gun <= 30):
        return await reply_error(update, "Gun 1-30 arasinda olmali.")
    miladi = date_from_hijri(hicri_yil, ay_idx, gun)
    if not miladi:
        return await reply_error(update, "Bu tarih hesap araliginin disinda.")
    ozel = OZEL.get((ay_idx, gun), "")
    text = ("Hicri > Miladi\n\nHicri  : " + str(gun) + " " + AYLAR_TR[ay_idx] + " " + str(hicri_yil)
            + "\nMiladi : " + str(miladi))
    if ozel:
        text += "\n>>> " + ozel
    await update.message.reply_text(text)

async def analiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Analiz hesaplaniyor, lutfen bekleyin...")
    lines   = ["Ramazan Dogruluk Analizi 1995-2025\n"]
    perfect = 0
    close   = 0
    total   = 0
    diffs   = []
    for year, real in sorted(REAL_RAMADAN.items()):
        m, _ = find_month_date(year, 8)
        if not m:
            lines.append("[?]  " + str(year) + " bulunamadi")
            continue
        diff = (m - real).days
        diffs.append(diff)
        if diff == 0:
            tag = "[OK]"
            perfect += 1
        elif abs(diff) == 1:
            tag = "[~1]"
            close += 1
        else:
            tag = "[X] "
        sign = "+" if diff >= 0 else ""
        lines.append(tag + " " + str(year) + " " + str(m) + " gercek:" + str(real) + " fark:" + sign + str(diff))
        total += 1
    acc0 = (perfect / total) * 100 if total else 0
    acc1 = ((perfect + close) / total) * 100 if total else 0
    ort  = sum(abs(d) for d in diffs) / len(diffs) if diffs else 0
    maks = max(abs(d) for d in diffs) if diffs else 0
    lines.append("\nOzet\n"
                 "Tam isabet (+-0) : %" + str(round(acc0,1)) + "\n"
                 "+-1 gun          : %" + str(round(acc1,1)) + "\n"
                 "Ort sapma        : " + str(round(ort,2)) + " gun\n"
                 "Maks sapma       : " + str(maks) + " gun\n"
                 "Test sayisi      : " + str(total))
    msg = "\n".join(lines)
    for chunk in [msg[i:i+4000] for i in range(0, len(msg), 4000)]:
        await update.message.reply_text(chunk)

async def karsilastir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        year = parse_year(context.args)
    except ValueError as e:
        return await reply_error(update, str(e))
    m_hesap, _ = find_month_date(year, 8)
    m_real     = REAL_RAMADAN.get(year)
    lines = [str(year) + " Ramazan Karsilastirmasi\n"]
    lines.append("Bot (Astronomik) : " + str(m_hesap))
    if m_real and m_hesap:
        diff = (m_hesap - m_real).days
        sign = "+" if diff >= 0 else ""
        lines.append("Gercek/Referans  : " + str(m_real) + " (fark: " + sign + str(diff) + " gun)")
    elif m_real:
        lines.append("Gercek/Referans  : " + str(m_real))
    else:
        lines.append("Gercek/Referans  : Veri yok")
    await update.message.reply_text("\n".join(lines))

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Hata: %s", context.error, exc_info=True)
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("Beklenmeyen hata. /yardim yazin.")

async def bilinmeyen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bilinmeyen komut. /yardim yazin.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
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
    app.run_polling()

if __name__ == "__main__":
    main()
