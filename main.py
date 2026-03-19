from datetime import datetime, timedelta
from skyfield.api import load, Topos

ts = load.timescale()
eph = load('de421.bsp')

earth = eph['earth']
moon = eph['moon']
sun = eph['sun']

def hilal_var(date):
    t = ts.utc(date.year, date.month, date.day, 18)

    loc = earth + Topos(latitude_degrees=21.4, longitude_degrees=39.8)

    alt,_,_ = loc.at(t).observe(moon).apparent().altaz()
    e = earth.at(t)
    elong = e.observe(moon).apparent().separation_from(
        e.observe(sun).apparent()
    ).degrees

    return alt.degrees > 0 and elong > 7

# 🔥 ANCHOR (senin dediğin doğru veri)
anchor_date = datetime(2026,3,19)
hicri_day = 30
hicri_month = 9  # Ramazan

# 🔥 GERİYE ANALİZ
def geriye_git(days=60):
    d = anchor_date
    gun = hicri_day
    ay = hicri_month

    for _ in range(days):
        print(d.date(), "→", gun, ay)

        d -= timedelta(days=1)
        gun -= 1

        if gun == 0:
            ay -= 1
            if ay == 0:
                ay = 12

            # hilal bulana kadar geri git
            for i in range(3):
                if hilal_var(d - timedelta(days=i)):
                    gun = 29
                    break
                else:
                    gun = 30

# 🔥 İLERİ ANALİZ
def ileri_git(days=60):
    d = anchor_date
    gun = hicri_day
    ay = hicri_month

    for _ in range(days):
        print(d.date(), "→", gun, ay)

        d += timedelta(days=1)
        gun += 1

        if gun > 30:
            if hilal_var(d):
                gun = 1
                ay += 1
                if ay > 12:
                    ay = 1
