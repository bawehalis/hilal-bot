import math
import logging
from datetime import datetime, timedelta, timezone, date

from skyfield.api import load
from skyfield.almanac import find_discrete, moon_phases, sunrise_sunset

from criteria import get_criterion, DEFAULT_CRITERION
from locations import get_all_locations

logger = logging.getLogger(__name__)

_ts    = None
_eph   = None
_earth = None
_moon  = None
_sun   = None

EPH_FILE = "de440.bsp"


def get_sf():
    global _ts, _eph, _earth, _moon, _sun
    if _ts is None:
        _ts = load.timescale()
        try:
            _eph = load(EPH_FILE)
            logger.info("%s yuklendi.", EPH_FILE)
        except Exception:
            logger.info("%s bulunamadi, de421.bsp deneniyor...", EPH_FILE)
            try:
                _eph = load("de421.bsp")
                logger.info("de421.bsp yuklendi.")
            except Exception:
                from skyfield.api import Loader
                _eph = Loader(".")("de421.bsp")
                logger.info("de421.bsp indirildi.")
        _earth = _eph["earth"]
        _moon  = _eph["moon"]
        _sun   = _eph["sun"]
    return _ts, _eph, _earth, _moon, _sun


_nm_cache = {}


def get_new_moons(start_year, end_year):
    key = (start_year, end_year)
    if key in _nm_cache:
        return _nm_cache[key]
    ts, eph, *_ = get_sf()
    t0 = ts.utc(start_year, 1, 1)
    t1 = ts.utc(end_year, 12, 31)
    times, phases = find_discrete(t0, t1, moon_phases(eph))
    result = [
        t.utc_datetime().replace(tzinfo=timezone.utc)
        for t, p in zip(times, phases)
        if p == 0
    ]
    _nm_cache[key] = result
    return result


def get_sunset_utc(loc, y, mo, d):
    ts, eph, *_ = get_sf()
    try:
        t0 = ts.utc(y, mo, d, 12)
        t1 = ts.utc(y, mo, d + 1, 6)
        times, events = find_discrete(t0, t1, sunrise_sunset(eph, loc))
        for t, e in zip(times, events):
            if e == 0:
                return t.utc_datetime().hour + t.utc_datetime().minute / 60.0
    except Exception:
        pass
    return 18.0


def check_hilal(d, nm, criterion_name=DEFAULT_CRITERION):
    ts, eph, earth, moon, sun = get_sf()
    criterion = get_criterion(criterion_name)
    locs = get_all_locations()

    best_q   = -99.0
    best_loc = ""
    gorunur  = False
    detaylar = {}

    for loc_name, loc in locs.items():
        sh = get_sunset_utc(loc, d.year, d.month, d.day)
        best_q_loc = -99.0
        best_alt   = -99.0
        best_elong = 0.0

        for off in range(15, 70, 5):
            hf = sh + off / 60.0
            h  = int(hf)
            mi = int((hf % 1) * 60)
            if h >= 24:
                break

            t     = ts.utc(d.year, d.month, d.day, h, mi)
            obs   = (earth + loc).at(t)
            m_app = obs.observe(moon).apparent()
            s_app = obs.observe(sun).apparent()
            alt_deg = m_app.altaz()[0].degrees
            elong   = m_app.separation_from(s_app).degrees

            if alt_deg <= 0:
                continue

            sunset_dt = datetime(d.year, d.month, d.day,
                                 int(sh), int((sh % 1) * 60),
                                 tzinfo=timezone.utc)
            age_hours = (sunset_dt - nm).total_seconds() / 3600.0

            if age_hours < 13.5:
                continue

            q = criterion.score(alt_deg, elong, age_hours)
            if q > best_q_loc:
                best_q_loc = q
                best_alt   = alt_deg
                best_elong = elong

        detaylar[loc_name] = {
            "alt":   best_alt,
            "elong": best_elong,
            "q":     best_q_loc,
        }

        if best_q_loc > best_q:
            best_q   = best_q_loc
            best_loc = loc_name

        if criterion.is_visible(best_alt, best_elong):
            gorunur = True

    return gorunur, best_q, best_loc, detaylar


def prev_conjunction(d):
    nms = get_new_moons(d.year - 1, d.year + 1)
    best = None
    for nm in nms:
        if nm.date() <= d:
            best = nm
        else:
            break
    return best


_month_cache = {}

ANCHOR_DATE  = date(2025, 3, 1)
ANCHOR_HIJRI = (1446, 8, 1)  # 1 Ramazan 1446


def find_month_start(nm, criterion_name=DEFAULT_CRITERION):
    """
    Konjunksiyon nm'ye gore ay basini bul.
    Konjunksiyon + 1 gun (D1) aksami hilal gorünürse D1,
    gorünmezse D2.
    """
    d1 = nm.date() + timedelta(days=1)
    d2 = nm.date() + timedelta(days=2)
    g, _, _, _ = check_hilal(d1, nm, criterion_name)
    return d1 if g else d2


def get_month_start(hicri_yil, hicri_ay, criterion_name=DEFAULT_CRITERION):
    """
    Verilen hicri yil ve aya ait ay basini dondur.
    Anchor noktasindan ileri veya geri adimlar atar.
    """
    cache_key = (hicri_yil, hicri_ay, criterion_name)
    if cache_key in _month_cache:
        return _month_cache[cache_key]

    # Anchor: 1 Ramazan 1446 = 1 Mart 2025
    anchor_total = ANCHOR_HIJRI[0] * 12 + ANCHOR_HIJRI[1]
    target_total = hicri_yil * 12 + hicri_ay
    delta_months = target_total - anchor_total

    if delta_months == 0:
        _month_cache[cache_key] = ANCHOR_DATE
        return ANCHOR_DATE

    # Tahmini miladi tarih (her hicri ay ~29.53 gun)
    est_date = ANCHOR_DATE + timedelta(days=round(delta_months * 29.53))

    # En yakin konjunksiyonu bul ve ay basini hesapla
    if delta_months > 0:
        # Ileri git
        current_date = ANCHOR_DATE
        current_total = anchor_total
        while current_total < target_total:
            nm = prev_conjunction(current_date + timedelta(days=28))
            if nm is None:
                break
            gun29 = current_date + timedelta(days=28)
            g, _, _, _ = check_hilal(gun29, nm, criterion_name)
            current_date = gun29 + timedelta(days=1 if g else 2)
            current_total += 1
    else:
        # Geri git
        current_date = ANCHOR_DATE
        current_total = anchor_total
        while current_total > target_total:
            # Bir ay geri: tahmini onceki ay basi
            prev_est = current_date - timedelta(days=30)
            nm = prev_conjunction(prev_est + timedelta(days=28))
            if nm is None:
                break
            gun29 = prev_est + timedelta(days=28)
            g, _, _, _ = check_hilal(gun29, nm, criterion_name)
            candidate = gun29 + timedelta(days=1 if g else 2)
            if candidate < current_date:
                current_date = candidate
            else:
                current_date = current_date - timedelta(days=30)
            current_total -= 1

    _month_cache[cache_key] = current_date
    return current_date


def miladi_to_hicri(d, criterion_name=DEFAULT_CRITERION):
    """Miladi tarihten Hicri gun, ay, yil dondur."""
    # Anchor'dan itibaren kac ay gectigi tahmin et
    delta_days  = (d - ANCHOR_DATE).days
    est_months  = int(delta_days / 29.53)

    anchor_total = ANCHOR_HIJRI[0] * 12 + ANCHOR_HIJRI[1]

    # Dogru ayi bul
    for offset in range(-2, 3):
        total = anchor_total + est_months + offset
        hyil  = total // 12
        hay   = total % 12
        if hay == 0:
            hyil -= 1
            hay   = 12

        start = get_month_start(hyil, hay, criterion_name)
        # Bir sonraki ay basi
        next_total = total + 1
        nyil = next_total // 12
        nay  = next_total % 12
        if nay == 0:
            nyil -= 1
            nay   = 12
        end = get_month_start(nyil, nay, criterion_name)

        if start <= d < end:
            gun = (d - start).days + 1
            return gun, hay, hyil

    # Fallback
    gun = (d - ANCHOR_DATE).days + 1
    return gun, ANCHOR_HIJRI[1], ANCHOR_HIJRI[0]


def hicri_to_miladi(hyil, hay, gun, criterion_name=DEFAULT_CRITERION):
    start = get_month_start(hyil, hay, criterion_name)
    if start is None:
        return None
    return start + timedelta(days=gun - 1)


AYLAR_TR = [
    "", "Muharrem", "Safer", "Rebi\u00fclevvel", "Rebi\u00fclahir",
    "Cemaziyelevvel", "Cemaziyelahir", "Recep",
    "\u015eaban", "Ramazan", "\u015eevval", "Zilkade", "Zilhicce"
]

AYLAR_ASCII = [
    "", "Muharrem", "Safer", "Rebiulevvel", "Rebiulahir",
    "Cemaziyelevvel", "Cemaziyelahir", "Recep",
    "Saban", "Ramazan", "Sevval", "Zilkade", "Zilhicce"
]


def ay_adi(hay, tr=True):
    if 1 <= hay <= 12:
        return AYLAR_TR[hay] if tr else AYLAR_ASCII[hay]
    return "?"


def ramazan_basi(yil, criterion_name=DEFAULT_CRITERION):
    return get_month_start(yil, 9, criterion_name)


def sevval_basi(yil, criterion_name=DEFAULT_CRITERION):
    return get_month_start(yil, 10, criterion_name)
