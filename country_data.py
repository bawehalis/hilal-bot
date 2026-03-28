import json
import os
from datetime import date

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "countries.json")

_data = None


def load_data():
    global _data
    if _data is None:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            _data = json.load(f)
    return _data


def get_countries():
    return list(load_data().keys())


def get_country_name(code):
    d = load_data()
    if code not in d:
        return None
    return d[code].get("name", code)


def get_ramazan(country_code, yil):
    d = load_data()
    if country_code not in d:
        return None
    r = d[country_code].get("ramazan", {}).get(str(yil))
    if r:
        parts = r.split("-")
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    return None


def get_bayram(country_code, yil):
    d = load_data()
    if country_code not in d:
        return None
    b = d[country_code].get("bayram", {}).get(str(yil))
    if b:
        parts = b.split("-")
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    return None


def get_all_years():
    d = load_data()
    years = set()
    for country in d.values():
        for y in country.get("ramazan", {}).keys():
            years.add(int(y))
    return sorted(years)


def add_country_year(country_code, yil, ramazan_str, bayram_str):
    d = load_data()
    if country_code not in d:
        raise ValueError(country_code + " bulunamadi.")
    d[country_code]["ramazan"][str(yil)] = ramazan_str
    d[country_code]["bayram"][str(yil)]  = bayram_str
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)
