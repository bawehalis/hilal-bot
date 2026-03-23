import os
import logging
import math
import asyncio
from datetime import datetime, timedelta, timezone, date

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from skyfield.api import load, wgs84
from skyfield.almanac import find_discrete, moon_phases, sunrise_sunset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise EnvironmentError("TOKEN env var missing")

_ts = _eph = _earth = _moon = _sun = None

def sf():
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

_nm_cache  = None
_cal_cache = None

def new_moons():
    global _nm_cache
    if _nm_cache: return _nm_cache
    ts, eph, *_ = sf()
    times, phases = find_discrete(ts.utc(1990,1,1), ts.utc(2040,12,31), moon_phases(eph))
    _nm_cache = [t.utc_datetime().replace(tzinfo=timezone.utc) for t,p in zip(times,phases) if p==0]
    return _nm_cache

LOCS = {
    "Mekke":    wgs84.latlon(21.4225, 39.8262),
    "Medine":   wgs84.latlon(24.4672, 39.6151),
    "Ankara":   wgs84.latlon(39.9334, 32.8597),
    "Istanbul": wgs84.latlon(41.0082, 28.9784),
    "Tahran":   wgs84.latlon(35.6892, 51.3890),
    "Kahire":   wgs84.latlon(30.0444, 31.2357),
    "Bagdat":   wgs84.latlon(33.3406, 44.4009),
    "Karaci":   wgs84.latlon(24.8607, 67.0011),
}

def sunset_utc(loc, y, mo, d):
    ts, eph, *_ = sf()
    try:
        times, events = find_discrete(
            ts.utc(y,mo,d,12), ts.utc(y,mo,d,23,59), sunrise_sunset(eph,loc)
        )
        for t,e in zip(times,events):
            if e==0: return t.utc_datetime().hour + t.utc_datetime().minute/60.0
    except: pass
    return 18.0

def odeh_q(alt, elong):
    return alt - (7.1651 - 6.3226*(elong*0.01) + 7.0482*(elong*0.01)**2 - 0.3014*(elong*0.01)**3)

def hilal(d, nm):
    ts, eph, earth, moon, sun = sf()
    best_q  = -99.0
    gorunur = False
    for loc in LOCS.values():
        sh = sunset_utc(loc, d.year, d.month, d.day)
        for off in range(15, 70, 5):
            hf = sh + off/60.0
            h, mi = int(hf), int((hf%1)*60)
            if h >= 24: break
            t     = ts.utc(d.year, d.month, d.day, h, mi)
            obs   = (earth + loc).at(t)
            m_app = obs.observe(moon).apparent()
            s_app = obs.observe(sun).apparent()
            alt_deg = m_app.altaz()[0].degrees
            elong   = m_app.separation_from(s_app).degrees
            if alt_deg <= 0: continue
            sunset_dt = datetime(d.year, d.month, d.day,
                                 int(sh), int((sh%1)*60), tzinfo=timezone.utc)
            if (sunset_dt - nm).total_seconds()/3600 < 13.5: continue
            q = odeh_q(alt_deg, elong)
            if q > best_q: best_q = q
            if q >= 0.0: gorunur = True
    return gorunur, best_q

def nm_onceki(d):
    """d tarihinden ONCE gerceklesen en son konjunksiyonu dondur."""
    nms = new_moons()
    best = None
    for nm in nms:
        if nm.date() <= d:
            best = nm
        else:
            break
    return best

def build_cal():
    global _cal_cache
    if _cal_cache: return _cal_cache
    logger.info("Takvim insa ediliyor...")
    nms = new_moons()

    # Bootstrap: ilk konjunksiyondan sonraki gun
    nm0 = nms[0]
    d1  = nm0.date() + timedelta(days=1)
    g, _ = hilal(d1, nm0)
    months = [d1 if g else d1 + timedelta(days=1)]

    for _ in range(620):
        prev  = months[-1]
        # Mevcut ayin 29. gunu (gun1=prev, gun29=prev+28)
        gun29 = prev + timedelta(days=28)
        # Bu gece icin dogru konjunksiyon: gun29'dan ONCE gerceklesen son nm
        nm = nm_onceki(gun29)
        if nm is None: break
        g, _ = hilal(gun29, nm)
        if g:
            months.append(gun29 + timedelta(days=1))   # ay 29 gun
        else:
            months.append(gun29 + timedelta(days=2))   # ay 30 gun
        if months[-1].year > 2040: break

    _cal_cache = months
    logger.info("Takvim V3 hazir: %d ay", len(_cal_cache))
    return _cal_cache

AYLAR_TR = [
    "Muharrem","Safer","Rebi\u00fclevvel","Rebi\u00fclahir",
    "Cemaziyelevvel","Cemaziyelahir","Recep",
    "\u015eaban","Ramazan","\u015eevval","Zilkade","Zilhicce"
]

def anchor():
    cal = build_cal()
    target = date(2025, 3, 1)
    idx = min(range(len(cal)), key=lambda i: abs((cal[i]-target).days))
    return idx, idx - 8

def hicri(d):
    cal = build_cal()
    ai, m1446 = anchor()
    cur = None
    for i, m in enumerate(cal):
        if m <= d: cur = (m, i)
    if not cur: return 0, "?", -1, 0
    start, idx = cur
    gun   = (d - start).days + 1
    delta = idx - m1446
    return gun, AYLAR_TR[delta%12], delta%12, 1446 + delta//12

def ay_basi(yil, ay_idx):
    cal = build_cal()
    ai, m1446 = anchor()
    for i, m in enumerate(cal):
        delta = i - m1446
        if delta%12 == ay_idx and m.year == yil:
            return m
    for i, m in enumerate(cal):
        delta = i - m1446
        if delta%12 == ay_idx and abs(m.year - yil) == 1:
            return m
    return None

def ramazan_basi(yil):
    return ay_basi(yil, 8)

def sevval_basi(yil):
    return ay_basi(yil, 9)

TR_RAM = {
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
SA_RAM = {
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
IR_RAM = {
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

TR_BAY = {
    1995:date(1995,3,3),   1996:date(1996,2,20),  1997:date(1997,2,9),
    1998:date(1998,1,30),  1999:date(1999,1,19),  2000:date(2000,1,8),
    2001:date(2001,12,17), 2002:date(2002,12,6),  2003:date(2003,11,26),
    2004:date(2004,11,14), 2005:date(2005,11,3),  2006:date(2006,10,24),
    2007:date(2007,10,13), 2008:date(2008,10,1),  2009:date(2009,9,20),
    2010:date(2010,9,10),  2011:date(2011,8,30),  2012:date(2012,8,19),
    2013:date(2013,8,8),   2014:date(2014,7,28),  2015:date(2015,7,17),
    2016:date(2016,7,6),   2017:date(2017,6,25),  2018:date(2018,6,15),
    2019:date(2019,6,4),   2020:date(2020,5,24),  2021:date(2021,5,13),
    2022:date(2022,5,2),   2023:date(2023,4,21),  2024:date(2024,4,10),
    2025:date(2025,3,30),
}
SA_BAY = {
    1995:date(1995,3,3),   1996:date(1996,2,19),  1997:date(1997,2,8),
    1998:date(1998,1,30),  1999:date(1999,1,19),  2000:date(2000,1,8),
    2001:date(2001,12,16), 2002:date(2002,12,6),  2003:date(2003,11,25),
    2004:date(2004,11,14), 2005:date(2005,11,3),  2006:date(2006,10,23),
    2007:date(2007,10,13), 2008:date(2008,10,1),  2009:date(2009,9,20),
    2010:date(2010,9,10),  2011:date(2011,8,30),  2012:date(2012,8,19),
    2013:date(2013,8,8),   2014:date(2014,7,28),  2015:date(2015,7,17),
    2016:date(2016,7,6),   2017:date(2017,6,25),  2018:date(2018,6,15),
    2019:date(2019,6,4),   2020:date(2020,5,24),  2021:date(2021,5,13),
    2022:date(2022,5,2),   2023:date(2023,4,21),  2024:date(2024,4,10),
    2025:date(2025,3,30),
}
IR_BAY = {
    1995:date(1995,3,4),   1996:date(1996,2,21),  1997:date(1997,2,10),
    1998:date(1998,1,31),  1999:date(1999,1,20),  2000:date(2000,1,9),
    2001:date(2001,12,17), 2002:date(2002,12,7),  2003:date(2003,11,26),
    2004:date(2004,11,14), 2005:date(2005,11,4),  2006:date(2006,10,24),
    2007:date(2007,10,13), 2008:date(2008,10,2),  2009:date(2009,9,20),
    2010:date(2010,9,10),  2011:date(2011,8,30),  2012:date(2012,8,19),
    2013:date(2013,8,8),   2014:date(2014,7,29),  2015:date(2015,7,18),
    2016:date(2016,7,6),   2017:date(2017,6,26),  2018:date(2018,6,15),
    2019:date(2019,6,4),   2020:date(2020,5,24),  2021:date(2021,5,13),
    2022:date(2022,5,3),   2023:date(2023,4,21),  2024:date(2024,4,10),
    2025:date(2025,3,30),
}

def fark(bot, ref):
    if ref is None: return "?"
    d = (bot - ref).days
    return ("+" if d >= 0 else "") + str(d)

def uzlasma(bot, tr, sa, ir):
    refs = [x for x in [tr, sa, ir] if x is not None]
    ayni = sum(1 for r in refs if r == bot)
    return ayni, len(refs)

def gun_sayisi_flag(n):
    if n == 29: return "29"
    if n == 30: return "30"
    return str(n) + "(!)"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "HICRI TAKVIM BOTU V3\n\n"
        "/bugun\n"
        "/analiz\n"
        "/karsilastir 2025\n"
    )

async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _cal_cache:
        return await update.message.reply_text("Takvim hazirlanıyor, bekleyin...")
    today = datetime.now(timezone.utc).date()
    gun, ay, ay_idx, hyil = hicri(today)
    await update.message.reply_text(
        "Bugun: " + str(today) + "\nHicri: " + str(gun) + " " + ay + " " + str(hyil)
    )

async def analiz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _cal_cache:
        return await update.message.reply_text("Takvim hazirlanıyor, bekleyin...")
    await update.message.reply_text("Analiz yapiliyor...")

    lines = [
        "RAMAZAN ANALIZI V3 — 1995-2025\n",
        "Baslangic ve Bitis kiyasi\n",
        "-"*60
    ]

    bot_ok = bot_sapma = 0
    tr_s = sa_s = ir_s = 0
    total = 0

    for yil in sorted(TR_RAM.keys()):
        bot_r = ramazan_basi(yil)
        bot_b = sevval_basi(yil)
        if not bot_r or not bot_b: continue

        bot_gun = (bot_b - bot_r).days
        tr_r = TR_RAM.get(yil); sa_r = SA_RAM.get(yil); ir_r = IR_RAM.get(yil)
        tr_b = TR_BAY.get(yil); sa_b = SA_BAY.get(yil); ir_b = IR_BAY.get(yil)

        tr_gun = (tr_b - tr_r).days if tr_r and tr_b else None
        sa_gun = (sa_b - sa_r).days if sa_r and sa_b else None
        ir_gun = (ir_b - ir_r).days if ir_r and ir_b else None

        r_ayni, r_top = uzlasma(bot_r, tr_r, sa_r, ir_r)
        b_ayni, b_top = uzlasma(bot_b, tr_b, sa_b, ir_b)

        if r_ayni >= 2 and b_ayni >= 2:
            durum = "OK"
            bot_ok += 1
            if tr_r and tr_r != bot_r: tr_s += 1
            if sa_r and sa_r != bot_r: sa_s += 1
            if ir_r and ir_r != bot_r: ir_s += 1
        elif r_ayni == r_top and b_ayni == b_top:
            durum = "OK"
            bot_ok += 1
        else:
            durum = "KONTROL"
            bot_sapma += 1

        total += 1
        lines.append(
            str(yil) + " "
            "RAM[" + fark(bot_r,tr_r) + "|" + fark(bot_r,sa_r) + "|" + fark(bot_r,ir_r) + "] "
            "BAY[" + fark(bot_b,tr_b) + "|" + fark(bot_b,sa_b) + "|" + fark(bot_b,ir_b) + "] "
            "GUN:" + gun_sayisi_flag(bot_gun) +
            "(TR:" + (gun_sayisi_flag(tr_gun) if tr_gun else "?") +
            " SA:" + (gun_sayisi_flag(sa_gun) if sa_gun else "?") +
            " IR:" + (gun_sayisi_flag(ir_gun) if ir_gun else "?") +
            ") " + durum
        )

    lines.append("\nOzet:")
    lines.append("Bot dogru   : " + str(bot_ok) + "/" + str(total) +
                 " (%" + str(round(bot_ok/total*100,1)) + ")")
    lines.append("Bot kontrol : " + str(bot_sapma) + "/" + str(total))
    lines.append("TR sapma    : " + str(tr_s))
    lines.append("SA sapma    : " + str(sa_s))
    lines.append("IR sapma    : " + str(ir_s))

    msg = "\n".join(lines)
    for chunk in [msg[i:i+4000] for i in range(0, len(msg), 4000)]:
        await update.message.reply_text(chunk)

async def karsilastir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _cal_cache:
        return await update.message.reply_text("Takvim hazirlanıyor, bekleyin...")
    try:
        yil = int(context.args[0]) if context.args else datetime.now().year
    except ValueError:
        return await update.message.reply_text("Ornek: /karsilastir 2025")

    bot_r = ramazan_basi(yil)
    bot_b = sevval_basi(yil)
    if not bot_r or not bot_b:
        return await update.message.reply_text("Veri bulunamadi.")

    bot_gun = (bot_b - bot_r).days
    tr_r = TR_RAM.get(yil); sa_r = SA_RAM.get(yil); ir_r = IR_RAM.get(yil)
    tr_b = TR_BAY.get(yil); sa_b = SA_BAY.get(yil); ir_b = IR_BAY.get(yil)

    tr_gun = (tr_b - tr_r).days if tr_r and tr_b else None
    sa_gun = (sa_b - sa_r).days if sa_r and sa_b else None
    ir_gun = (ir_b - ir_r).days if ir_r and ir_b else None

    r_ayni, r_top = uzlasma(bot_r, tr_r, sa_r, ir_r)
    b_ayni, b_top = uzlasma(bot_b, tr_b, sa_b, ir_b)

    lines = [
        str(yil) + " Detayli Karsilastirma\n",
        "--- RAMAZAN BASLANGICI ---",
        "Bot : " + str(bot_r),
        "TR  : " + str(tr_r) + "  " + fark(bot_r, tr_r),
        "SA  : " + str(sa_r) + "  " + fark(bot_r, sa_r),
        "IR  : " + str(ir_r) + "  " + fark(bot_r, ir_r),
        "Uzlasma: " + str(r_ayni) + "/" + str(r_top),
        "",
        "--- RAMAZAN BITISI (1 Sevval) ---",
        "Bot : " + str(bot_b),
        "TR  : " + str(tr_b) + "  " + fark(bot_b, tr_b),
        "SA  : " + str(sa_b) + "  " + fark(bot_b, sa_b),
        "IR  : " + str(ir_b) + "  " + fark(bot_b, ir_b),
        "Uzlasma: " + str(b_ayni) + "/" + str(b_top),
        "",
        "--- RAMAZAN GUN SAYISI ---",
        "Bot : " + gun_sayisi_flag(bot_gun),
        "TR  : " + (gun_sayisi_flag(tr_gun) if tr_gun else "?"),
        "SA  : " + (gun_sayisi_flag(sa_gun) if sa_gun else "?"),
        "IR  : " + (gun_sayisi_flag(ir_gun) if ir_gun else "?"),
    ]

    if r_ayni >= 2 and b_ayni >= 2:
        lines.append("\nSonuc: Bot dogru.")
    else:
        farklilar = []
        if tr_r and (tr_r != bot_r or (tr_b and tr_b != bot_b)): farklilar.append("TR")
        if sa_r and (sa_r != bot_r or (sa_b and sa_b != bot_b)): farklilar.append("SA")
        if ir_r and (ir_r != bot_r or (ir_b and ir_b != bot_b)): farklilar.append("IR")
        if len(farklilar) >= 2:
            lines.append("\nSonuc: Bot kontrol edilmeli.")
        else:
            lines.append("\nSonuc: " + ", ".join(farklilar) + " sapti, bot muhtemelen dogru.")

    await update.message.reply_text("\n".join(lines))

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Hata: %s", context.error, exc_info=True)
    if isinstance(update, Update) and update.message:
        await update.message.reply_text("Hata olustu.")

async def warm_up(app):
    logger.info("Takvim arka planda hazirlaniyor...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, build_cal)
    logger.info("Takvim hazir.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start",       start))
    app.add_handler(CommandHandler("bugun",       bugun))
    app.add_handler(CommandHandler("analiz",      analiz))
    app.add_handler(CommandHandler("karsilastir", karsilastir))
    app.add_error_handler(error_handler)
    app.post_init = warm_up
    logger.info("Bot V3 baslatildi.")
    app.run_polling()

if __name__ == "__main__":
    main()
