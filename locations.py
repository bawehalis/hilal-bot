from skyfield.api import wgs84

DEFAULT_LOCATIONS = {
    "Mekke":    wgs84.latlon(21.4225,  39.8262),
    "Medine":   wgs84.latlon(24.4672,  39.6151),
    "Ankara":   wgs84.latlon(39.9334,  32.8597),
    "Istanbul": wgs84.latlon(41.0082,  28.9784),
    "Tahran":   wgs84.latlon(35.6892,  51.3890),
    "Kahire":   wgs84.latlon(30.0444,  31.2357),
    "Bagdat":   wgs84.latlon(33.3406,  44.4009),
    "Karaci":   wgs84.latlon(24.8607,  67.0011),
}

_user_locations = {}


def get_all_locations():
    locs = {}
    locs.update(DEFAULT_LOCATIONS)
    locs.update(_user_locations)
    return locs


def add_location(name, lat, lon):
    if not (-90 <= lat <= 90):
        raise ValueError("Enlem -90 ile 90 arasinda olmali.")
    if not (-180 <= lon <= 180):
        raise ValueError("Boylam -180 ile 180 arasinda olmali.")
    _user_locations[name] = wgs84.latlon(lat, lon)


def remove_location(name):
    if name in DEFAULT_LOCATIONS:
        raise ValueError(name + " varsayilan konum, silinemez.")
    if name not in _user_locations:
        raise ValueError(name + " bulunamadi.")
    del _user_locations[name]


def list_locations():
    lines = ["Varsayilan Konumlar:"]
    for k, v in DEFAULT_LOCATIONS.items():
        lines.append("  " + k + ": " + str(round(v.latitude.degrees, 4)) +
                     ", " + str(round(v.longitude.degrees, 4)))
    if _user_locations:
        lines.append("Kullanici Konumlari:")
        for k, v in _user_locations.items():
            lines.append("  " + k + ": " + str(round(v.latitude.degrees, 4)) +
                         ", " + str(round(v.longitude.degrees, 4)))
    return "\n".join(lines)
