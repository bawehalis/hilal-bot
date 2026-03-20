import os
import logging
import math
import asyncio
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

_ts    = None
_eph   = None
_earth = None
_moon  = None
_sun   = None

def get_skyfield():
    global _ts, _eph, _earth, _moon, _sun
    if _ts is None:
        _ts = load.timescale()
        try:
            _eph = load("de421.bsp")
        except Exception:
            from skyfield.api import Loader
            _eph = Loader(".")("de421.bsp")
        _earth = _eph["earth"]
        _moon  = _eph["moon"]
        _sun   = _eph["sun"]
    return _ts, _eph, _earth, _moon, _sun

_new_moons_cache = None
_months_cache    = None
_anchor_cache    = None

def get_new_moons():
    global _new_moons_cache
    if _new_moons_cache is not None:
        return _new_moons_cache
    ts, eph, earth, moon, sun = get_skyfield()
    t0 = ts.utc(1993, 1, 1)
    t1 = ts.utc(2040, 12, 31)
    times, phases = find_discrete(t0, t1, moon_phases(eph))
    _new_moons_cache = [
        t.utc_datetime().replace(tzinfo=timezone.utc)
        for t, p in zip(times, phases)
        if p == 0
    ]
    return _new_moons_cache

def get_months():
    global _months_cache
    if _months_cache is not None:
        return _months_cache
    logger.info("Takvim insa ediliyor...")
    new_moons = get_new_moons()
    months = []
    prev_start = None
    for nm in new_moons:
        start = find_month_start(nm, prev_start)
        months.append(start)
        prev_start = start
    _months_cache = sorted(months)
    logger.info("Takvim hazir: %d ay.", len(_months_cache))
    return _months_cache

def get_anchor():
    global _anchor_cache
    if _anchor_cache is not None:
        return _anchor_cache
    months = get_months()
    anchor_target = datetime(2025, 3, 1).date()
    anchor_index  = min(range(len(months)), key=lambda i: abs((months[i] - anchor_target).days))
    muharrem_1446 = anchor_index - 8
    _anchor_cache = (anchor_index, muharrem_1446)
    return _anchor_cache

GOZLEM_NOKTALARI = {
    "Mekke":    wgs84.latlon(21.4225, 39.8262),
    "Medine":   wgs84.latlon(24.4672, 39.6151),
    "Ankara":   wgs84.latlon(39.9334, 32.8597),
    "Istanbul": wgs84.latlon(41.0082, 28.9784),
    "Tahran":   wgs84.latlon(35.6892, 51.3890),
    "Kahire":   wgs84.latlon(30.0444, 31.2357),
    "Bagdat":   wgs84.latlon(33.3406, 44.4009),
    "Karaci":   wgs84.latlon(24.8607, 67.0011),
}

def get_sunset_utc(loc, year, month, day):
    ts, eph, earth, moon, sun = get_skyfield()
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

def odeh_q(alt_deg, elong_deg):
    W    = elong_deg
    ARCV = alt_deg
    return ARCV - (7.1651 - 6.3226*(W*0.01) + 7.0482*(W*0.01)**2 - 0.3014*(W*0.01)**3)

def evaluate_location(loc, check_date, nm):
    ts, eph, earth, moon, sun = get_skyfield()
    sunset_h   = get_sunset_utc(loc, check_date.year, check_date.month, check_date.day)
    best_q     = -99.0
    best_alt   = -99.0
    best_elong = 0.0

    for offset_min in range(15, 70, 5):
        hf     = sunset_h + offset_min / 60.0
        hour   = int(hf)
        minute = int((hf - hour) * 60)
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

        # Konjunksiyondan sonra sunset aninda ay en az 13.5 saat olmali
        sunset_dt = datetime(
            check_date.year, check_date.month, check_date.day,
            int(sunset_h), int((sunset_h % 1) * 60),
            tzinfo=timezone.utc
        )
        if (sunset_dt - nm).total_seconds() / 3600.0 < 13.5:
            continue

        q = odeh_q(alt_deg, elong)
        if q > best_q:
            best_q     = q
            best_alt   = alt_deg
            best_elong = elong

    return {"alt": best_alt, "elong": best_elong, "q": best_q}

def hilal_gorunur_global(check_date, nm):
    best_q   = -99.0
    best_loc = ""
    gorunur  = False
    detaylar = {}

    for loc_name, loc in GOZLEM_NOKTALARI.items():
        p = evaluate_location(loc, check_date, nm)
        detaylar[loc_name] = p
        if p["q"] > best_q:
            best_q   = p["q"]
            best_loc = loc_name
        if p["q"] >= 0.0:
            gorunur = True

    return gorunur, best_q, best_loc, detaylar

def find_month_start(nm, prev_month_start=None):
    """
    Dogru Hicri takvim mantiği:

    Onceki ayin 29. gunu aksami hilal ara.
    Gorunurse: yeni ay 30. gunün ertesi baslar (onceki ay 29 gun).
    Gorunmezse: onceki ay 30 gune tamamlanir, yeni ay 31. gun baslar.

    Eger prev_month_start bilinmiyorsa (ilk ay):
    Konjunksiyon + 1 gun = D1, konjunksiyon + 2 gun = D2 mantigi.
    """
    if prev_month_start is None:
        # Bootstrap: ilk ay icin klasik D1/D2 mantigi
        d1 = nm.date() + timedelta(days=1)
        gorunur, q, loc, _ = hilal_gorunur_global(d1, nm)
        if gorunur:
            return d1
        return d1 + timedelta(days=1)

    # Onceki ayin 29. gunu
    gun29 = prev_month_start + timedelta(days=28)  # 0-index: gun 1 = prev_start, gun 29 = +28

    # O gece hilal gorünür mü?
    gorunur, q, loc, _ = hilal_gorunur_global(gun29, nm)

    if gorunur:
        # Hilal goruldu: yeni ay gun29'un ertesi gunü baslar
        return gun29 + timedelta(days=1)
    else:
        # Hilal gorulmedi: ay 30 gune tamamlandi
        return gun29 + timedelta(days=2)

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

def get_hijri(check_date):
    months = get_months()
    anchor_index, muharrem_1446 = get_anchor()
    current = None
    for i, m in enumerate(months):
        if m <= check_date:
            current = (m, i)
    if not current:
        return 0, "?", -1, 0
    start, idx = current
    gun       = (check_date - start).days + 1
    delta     = idx - muharrem_1446
    ay_index  = delta % 12
    hicri_yil = 1446 + delta // 12
    return gun, AYLAR_TR[ay_index], ay_index, hicri_yil

def date_from_hijri(hicri_yil, ay_index, gun):
    months = get_months()
    anchor_index, muharrem_1446 = get_anchor()
    delta      = (hicri_yil - 1446) * 12 + ay_index
    target_idx = muharrem_1446 + delta
    if target_idx < 0 or target_idx >= len(months):
        return None
    return months[target_idx] + timedelta(days=gun - 1)

def find_month_date(year_miladi, ay_index):
    months = get_months()
    anchor_index, muharrem_1446 = get_anchor()
    candidates = []
    for i, m in enumerate(months):
        delta = i - muharrem_1446
        if delta % 12 == ay_index % 12:
            candidates.append((m, i))
    for m, i in candidates:
        if m.year == year_miladi:
            return m, i
    for m, i in candidates:
        if abs(m.year - year_miladi) == 1:
            return m, i
    return None, None

RAMAZAN_TURKIYE = {
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

RAMAZAN_SUUDI = {
    1995:date(1995,2,1),  1996:date(1996,1,21), 1997:date(1997,1,10),
    1998:date(1998,12,20),1999:date(1999,12,9), 2000:date(2000,11,27),
    2001:date(2001,11,16),2002:date(2002,11,6), 2003:date(2003,10,26),
    2004:date(2004,10,15),2005:date(2005,10,4), 2006:date(2006,9,23),
    2007:date(2007,9,13), 2008:date(2008,9,1),  2009:date(2009,8,22),
    2010:date(2010,8,11), 2011:date(2011,8,1),  2012:date(2012,7,20),
    2013:date(2013,7,9),  2014:date(2014,6,28), 2015:date(2015,6,18),
    2016:date(2016,6,6),  2017:date(2017,5,27), 2018:date(2018,5,16),
    2019:date(2019,5,5),  2020:date(2020,4,24), 2021:date(2021,4,13),
    2022:date(2022,4,2),  2023:date(2023,3,23), 2024:date(2024,3,11),
    2025:date(2025,3,1),
}

RAMAZAN_IRAN = {
    1995:date(1995,2,1),  1996:date(1996,1,22), 1997:date(1997,1,11),
    1998:date(1998,12,21),1999:date(1999,12,10),2000:date(2000,11,28),
    2001:date(2001,11,17),2002:date(2002,11,7), 2003:date(2003,10,27),
    2004:date(2004,10,15),2005:date(2005,10,5), 2006:date(2006,9,24),
    2007:date(2007,9,13), 2008:date(2008,9,2),  2009:date(2009,8,22),
    2010:date(2010,8,11), 2011:date(2011,8,1),  2012:date(2012,7,20),
    2013:date(2013,7,9),  2014:date(2014,6,29), 2015:date(2015,6,18),
    2016:date(2016,6,7),  2017:date(2017,5,27), 2018:date(2018,5,17),
    2019:date(2019,5,6),  2020:date(2020,4,24), 2021:date(2021,4,13),
    2022:date(2022,4,2),  2023:date(2023,3,23), 2024:date(2024,3,11),
    2025:date(2025,3,1),
}

def parse_year(args, min_y=1995, max_y=2040):
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

def fark_str(bot, ref):
    if ref is None:
        return "?"
    d = (bot - ref).days
    return ("+" if d >= 0 else "") + str(d)

def cache_hazir():
    return _months_cache is not None

HAZIR_DEGIL_MSG = "Takvim hazırlaniyor, lutfen 1-2 dakika bekleyip tekrar deneyin."

HELP_TEXT = (
    "HICRI TAKVIM BOTU\n\n"
    "/bugun                          Bugunun Hicri tarihi\n"
    "/yil 2027                       Yil bazli takvim\n"
    "/ramazan 2027                   Ramazan baslangici\n"
    "/arefe 2027                     Kurban Bayrami\n"
    "/bayramlar 2027                 Tum dini gunler\n"
    "/kacgun                         Ramazana kac gun kaldi\n"
    "/hilal                          Bugun hilal durumu\n"
    "/miladiden 2026-03-20           Miladi > Hicri\n"
    "/hicridenmiladi 15 Ramazan 1446 Hicri > Miladi\n"
    "/analiz                         3 ulke karsilastirma\n"
    "/karsilastir 2025               Yil bazli karsilastirma\n"
    "/ayuzunluklari 2025             Ay gun sayilari\n"
    "/yardim                         Bu menu\n"
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)

async def yardim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)

async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not cache_hazir():
        return await update.message.reply_text(HAZIR_DEGIL_MSG)
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
    if not cache_hazir():
        return await update.message.reply_text(HAZIR_DEGIL_MSG)
    months = get_months()
    anchor_index, muharrem_1446 = get_anchor()
    lines = [str(year) + " Yili Hicri Ay Baslari\n"]
    found = False
    for i, m in enumerate(months):
        if m.year == year:
            delta      = i - muharrem_1446
            idx        = delta % 12
            hyil       = 1446 + delta // 12
            gun_sayisi = (months[i+1] - m).days if i+1 < len(months) else "?"
            lines.append(AYLAR_TR[idx] + " " + str(hyil) + ": " + str(m) + " (" + str(gun_sayisi) + " gun)")
            found = True
    if not found:
        lines.append("Bu yil icin veri bulunamadi.")
    await update.message.reply_text("\n".join(lines))

async def ramazan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        year = parse_year(context.args)
    except ValueError as e:
        return await reply_error(update, str(e))
    if not cache_hazir():
        return await update.message.reply_text(HAZIR_DEGIL_MSG)
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
    if not cache_hazir():
        return await update.message.reply_text(HAZIR_DEGIL_MSG)
    m, _ = find_month_date(year, 11)
    if m:
        text = ("Kurban Bayrami " + str(year) + "\n"
                "Zilhicce 1 : " + str(m) + "\n"
                "Arefe      : " + str(m + timedelta(days=8)) + "\n"
                "Bayram 1   : " + str(m + timedelta(days=9)) + "\n"
                "Bayram 2   : " + str(m + timedelta(days=10)) + "\n"
                "Bayram 3   : " + str(m + timedelta(days=11)) + "\n"
                "Bayram 4   : " + str(m + timedelta(days=12)))
    else:
        text = str(year) + " icin veri bulunamadi."
    await update.message.reply_text(text)

async def bayramlar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        year = parse_year(context.args)
    except ValueError as e:
        return await reply_error(update, str(e))
    if not cache_hazir():
        return await update.message.reply_text(HAZIR_DEGIL_MSG)
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
                lines.append(str(hedef) + "  " + isim)
                found = True
    if not found:
        lines.append("Bu yil icin veri bulunamadi.")
    await update.message.reply_text("\n".join(lines))

async def kacgun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not cache_hazir():
        return await update.message.reply_text(HAZIR_DEGIL_MSG)
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
    if _new_moons_cache is None:
        return await update.message.reply_text(HAZIR_DEGIL_MSG)
    today = datetime.now(timezone.utc).date()
    nm = None
    for t in reversed(_new_moons_cache):
        if t.date() <= today:
            nm = t
            break
    if not nm:
        return await reply_error(update, "Yeni ay verisi bulunamadi.")
    age_hours = (today - nm.date()).days * 24
    await update.message.reply_text("Hilal hesaplaniyor...")
    loop = asyncio.get_event_loop()
    gorunur, best_q, best_loc, detaylar = await loop.run_in_executor(
        None, hilal_gorunur_global, today, nm
    )
    if best_q >= 0.0:
        durum = "Acik gozle gorunur"
    elif best_q >= -0.96:
        durum = "Optik aracla gorunebilir"
    else:
        durum = "Gorunmez"
    lines = ["Hilal Durumu - " + str(today) + "\n",
             "Yeni Ay : " + str(nm.date()),
             "Ay Yasi : " + str(int(age_hours)) + " saat",
             "En iyi  : " + best_loc,
             "ODEH-q  : " + str(round(best_q, 3)),
             "Durum   : " + durum,
             "\nKonum Detaylari:"]
    for loc_name, p in detaylar.items():
        if p["alt"] > 0:
            lines.append(loc_name + ": alt=" + str(round(p["alt"],1)) +
                         " elong=" + str(round(p["elong"],1)) +
                         " q=" + str(round(p["q"],3)))
    await update.message.reply_text("\n".join(lines))

async def miladiden(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        tarih = parse_date_arg(context.args)
    except ValueError as e:
        return await reply_error(update, str(e))
    if not cache_hazir():
        return await update.message.reply_text(HAZIR_DEGIL_MSG)
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
    if not cache_hazir():
        return await update.message.reply_text(HAZIR_DEGIL_MSG)
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
    if not cache_hazir():
        return await update.message.reply_text(HAZIR_DEGIL_MSG)
    await update.message.reply_text("Analiz hesaplaniyor, lutfen bekleyin...")
    lines = ["RAMAZAN ANALIZI 1995-2025\n"
             "Bot | TR | SA | IR | [TR|SA|IR]\n"
             + "-"*60]
    tr_ok = sa_ok = ir_ok = 0
    total = 0
    for year in sorted(RAMAZAN_TURKIYE.keys()):
        bot_m, _ = find_month_date(year, 8)
        if not bot_m:
            continue
        tr = RAMAZAN_TURKIYE.get(year)
        sa = RAMAZAN_SUUDI.get(year)
        ir = RAMAZAN_IRAN.get(year)
        tr_d = fark_str(bot_m, tr)
        sa_d = fark_str(bot_m, sa)
        ir_d = fark_str(bot_m, ir)
        if tr and (bot_m - tr).days == 0: tr_ok += 1
        if sa and (bot_m - sa).days == 0: sa_ok += 1
        if ir and (bot_m - ir).days == 0: ir_ok += 1
        total += 1
        lines.append(str(year) + " Bot:" + str(bot_m) +
                     " TR:" + str(tr) +
                     " SA:" + str(sa) +
                     " IR:" + str(ir) +
                     " [" + tr_d + "|" + sa_d + "|" + ir_d + "]")
    lines.append("\nOzet (tam isabet):")
    lines.append("Turkiye : %" + str(round(tr_ok/total*100, 1)))
    lines.append("Suudi   : %" + str(round(sa_ok/total*100, 1)))
    lines.append("Iran    : %" + str(round(ir_ok/total*100, 1)))
    lines.append("Test    : " + str(total) + " yil")
    msg = "\n".join(lines)
    for chunk in [msg[i:i+4000] for i in range(0, len(msg), 4000)]:
        await update.message.reply_text(chunk)

async def karsilastir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        year = parse_year(context.args)
    except ValueError as e:
        return await reply_error(update, str(e))
    if not cache_hazir():
        return await update.message.reply_text(HAZIR_DEGIL_MSG)
    bot_m, _ = find_month_date(year, 8)
    tr = RAMAZAN_TURKIYE.get(year)
    sa = RAMAZAN_SUUDI.get(year)
    ir = RAMAZAN_IRAN.get(year)
    lines = [str(year) + " Ramazan Karsilastirmasi\n",
             "Astronomik Bot : " + str(bot_m),
             "Turkiye (TR)   : " + str(tr) + "  fark: " + fark_str(bot_m, tr),
             "Suudi Arabistan: " + str(sa) + "  fark: " + fark_str(bot_m, sa),
             "Iran           : " + str(ir) + "  fark: " + fark_str(bot_m, ir)]
    await update.message.reply_text("\n".join(lines))

async def ayuzunluklari(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        year = parse_year(context.args)
    except ValueError as e:
        return await reply_error(update, str(e))
    if not cache_hazir():
        return await update.message.reply_text(HAZIR_DEGIL_MSG)
    months = get_months()
    anchor_index, muharrem_1446 = get_anchor()
    lines = [str(year) + " Ay Uzunluklari\n"]
    found = False
    for i, m in enumerate(months):
        if m.year == year and i+1 < len(months):
            delta      = i - muharrem_1446
            idx        = delta % 12
            hyil       = 1446 + delta // 12
            gun_sayisi = (months[i+1] - m).days
            flag       = "" if gun_sayisi in (29, 30) else " <<ANORMAL!"
            lines.append(AYLAR_TR[idx] + " " + str(hyil) + ": " + str(m) +
                         " -> " + str(gun_sayisi) + " gun" + flag)
            found = True
    if not found:
        lines.append("Bu yil icin veri bulunamadi.")
    await update.message.reply_text("\n".join(lines))

async def warm_up_cache(app):
    logger.info("Takvim arka planda hazirlanıyor...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, get_months)
    logger.info("Takvim hazir.")

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
    app.add_handler(CommandHandler("ayuzunluklari",  ayuzunluklari))
    app.add_handler(MessageHandler(filters.COMMAND,  bilinmeyen))
    app.add_error_handler(error_handler)
    app.post_init = warm_up_cache
    logger.info("Bot baslatildi.")
    app.run_polling()

if __name__ == "__main__":
    main()
