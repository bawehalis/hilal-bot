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
            h, mi = int(hf), int((hf % 1)*60)
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

            # Konjunksiyondan sonra sunset aninda ay en az 13.5 saat olmali
            # 2023 ve 2013 gibi gec konjunksiyon durumlarini yakalar
            if (sunset_dt - nm).total_seconds()/3600 < 13.5: continue

            q = odeh_q(alt_deg, elong)
            if q > best_q: best_q = q
            if q >= 0.0: gorunur = True

    return gorunur, best_q

def nm_bul(d):
    """d tarihinden once veya o gune en yakin (sonraki) konjunksiyonu bul."""
    nms = new_moons()
    best = None
    for nm in nms:
        if nm.date() >= d - timedelta(days=3):
            best = nm
            break
    return best

def build_cal():
    global _cal_cache
    if _cal_cache: return _cal_cache
    logger.info("Takvim insa ediliyor...")
    nms = new_moons()

    # Bootstrap
    nm0 = nms[0]
    d1  = nm0.date() + timedelta(days=1)
    g, _ = hilal(d1, nm0)
    months = [d1 if g else d1 + timedelta(days=1)]

    for _ in range(620):
        prev  = months[-1]
        gun29 = prev + timedelta(days=28)
        nm    = nm_bul(gun29)
        if nm is None: break
        g, _ = hilal(gun29, nm)
        months.append(gun29 + timedelta(days=1 if g else 2))
        if months[-1].year > 2040: break

    _cal_cache = months
    logger.info("Takvim hazir: %d ay", len(_cal_cache))
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

def ramazan_basi(yil):
    cal = build_cal()
    ai, m1446 = anchor()
    for i, m in enumerate(cal):
        delta = i - m1446
        if delta%12 == 8 and m.year == yil:
            return m
    for i, m in enumerate(cal):
        delta = i - m1446
        if delta%12 == 8 and abs(m.year - yil) == 1:
            return m
    return None

TR = {
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
SA = {
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
IR = {
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

def fark(bot, ref):
    if ref is None: return "?"
    d = (bot - ref).days
    return ("+" if d >= 0 else "") + str(d)

def uzlasma(bot, tr, sa, ir):
    refs = [x for x in [tr, sa, ir] if x is not None]
    ayni = sum(1 for r in refs if r == bot)
    return ayni, len(refs)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "HICRI TAKVIM BOTU\n\n"
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
        "RAMAZAN ANALIZI 1995-2025\n",
        "Yil  Bot         TR          SA          IR          [TR|SA|IR]  Durum",
        "-"*75
    ]

    bot_dogru  = 0
    bot_sapma  = 0
    ir_sapma   = 0
    sa_sapma   = 0
    tr_sapma   = 0
    total      = 0

    for yil in sorted(TR.keys()):
        bot = ramazan_basi(yil)
        if not bot: continue
        tr = TR.get(yil)
        sa = SA.get(yil)
        ir = IR.get(yil)

        tr_d = fark(bot, tr)
        sa_d = fark(bot, sa)
        ir_d = fark(bot, ir)

        ayni, toplam = uzlasma(bot, tr, sa, ir)

        if ayni == toplam:
            durum = "OK"
            bot_dogru += 1
        elif ayni >= 2:
            durum = "OK"
            bot_dogru += 1
            if tr and tr != bot: tr_sapma += 1
            if sa and sa != bot: sa_sapma += 1
            if ir and ir != bot: ir_sapma += 1
        elif ayni == 1:
            durum = "KONTROL"
            bot_sapma += 1
        else:
            durum = "BOT-SAPTI"
            bot_sapma += 1

        total += 1
        lines.append(
            str(yil) + "  " + str(bot) + "  " + str(tr) + "  " +
            str(sa)  + "  " + str(ir)  + "  " +
            "[" + tr_d + "|" + sa_d + "|" + ir_d + "]  " + durum
        )

    lines.append("\nOzet:")
    lines.append("Bot dogru (cogunlukla)  : " + str(bot_dogru) + "/" + str(total) +
                 " (%" + str(round(bot_dogru/total*100,1)) + ")")
    lines.append("Bot sapma (kontrol et) : " + str(bot_sapma) + "/" + str(total))
    lines.append("TR sapma sayisi        : " + str(tr_sapma))
    lines.append("SA sapma sayisi        : " + str(sa_sapma))
    lines.append("IR sapma sayisi        : " + str(ir_sapma))

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

    bot = ramazan_basi(yil)
    tr  = TR.get(yil)
    sa  = SA.get(yil)
    ir  = IR.get(yil)

    ayni, toplam = uzlasma(bot, tr, sa, ir)

    lines = [
        str(yil) + " Ramazan Karsilastirmasi\n",
        "Astronomik Bot : " + str(bot),
        "Turkiye   (TR) : " + str(tr) + "  " + fark(bot, tr),
        "Suudi     (SA) : " + str(sa) + "  " + fark(bot, sa),
        "Iran      (IR) : " + str(ir) + "  " + fark(bot, ir),
        "\nUzlasma: " + str(ayni) + "/" + str(toplam) + " ulke bot ile ayni",
    ]

    if ayni == toplam:
        lines.append("Sonuc: Tum kaynaklar ayni gunu gosteriyor.")
    elif ayni >= 2:
        farklilar = []
        if tr and tr != bot: farklilar.append("TR")
        if sa and sa != bot: farklilar.append("SA")
        if ir and ir != bot: farklilar.append("IR")
        lines.append("Sonuc: " + ", ".join(farklilar) + " farkli — muhtemelen o kaynak sapti.")
    else:
        lines.append("Sonuc: Net uzlasma yok, bot degerini kontrol et.")

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
    logger.info("Bot baslatildi.")
    app.run_polling()

if __name__ == "__main__":
    main()
