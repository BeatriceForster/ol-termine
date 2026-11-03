"""Gemeinsame Logik zum Holen/Parsen der o-l.ch-Terminliste und zum
ungefaehren Geocoding fehlender Koordinaten. Wird sowohl vom lokalen
Dev-Server (server.py) als auch vom GitHub-Actions-Datengenerator
(update_data.py) verwendet.
"""
import html
import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SOURCE_URL = "https://o-l.ch/cgi-bin/fixtures"
DETAIL_URL = "https://o-l.ch/cgi-bin/fixtures?mode=show&unique_id={uid}"
GEOCODE_URL = "https://api3.geo.admin.ch/rest/services/api/SearchServer"
GEOCODE_CACHE_FILE = Path(__file__).parent / "geocode-cache.json"

# Grobe Zentren pro OL-Region + Toleranzradius (km), um offensichtlich falsche
# Geocoding-Treffer zu verwerfen (z.B. ein gleichnamiger Ort im falschen Kanton).
# "AUSL." (Ausland) wird bewusst nicht geocodiert, da der Dienst nur Schweizer Orte kennt.
REGION_CENTROID = {
    "ZH/SH": (47.45, 8.65, 70),
    "AG": (47.40, 8.15, 55),
    "BE/SO": (47.05, 7.55, 90),
    "GL/GR": (46.85, 9.50, 110),
    "NOS": (47.45, 9.20, 60),
    "NWS": (47.50, 7.70, 55),
    "SR": (46.55, 6.80, 150),
    "TI": (46.20, 8.90, 60),
    "ZS": (47.00, 8.30, 70),
}

LINE_RE = re.compile(
    r'(?P<weekday>\w{2}) (?P<day>\d{2})\.(?P<month>\d{2})\.\s+'
    r'(?P<region>\S+)\s+'
    r'(?P<code>[^\s<]+)?\s*'
    r'<a href="fixtures\?&mode=show&unique_id=(?P<uid>\d+)">(?P<name>.*?)</a>'
    r'(?P<rest>.*)'
)

TERRAIN_BY_ICON = {
    "\U0001F332": "wald",    # 🌲
    "\U0001F3E0": "stadt",   # 🏠
    "\U0001F3E1": "mix",     # 🏡
}


def lv03_to_wgs84(e, n):
    """Approximate CH1903/LV03 -> WGS84 conversion (swisstopo formula, ~1m accuracy)."""
    y = (e - 600000) / 1000000
    x = (n - 200000) / 1000000
    lon = 2.6779094 + 4.728982 * y + 0.791484 * y * x + 0.1306 * y * x ** 2 - 0.0436 * y ** 3
    lat = 16.9023892 + 3.238272 * x - 0.270978 * y ** 2 - 0.002528 * x ** 2 - 0.0447 * y ** 2 * x - 0.0140 * x ** 3
    return lat * 100 / 36, lon * 100 / 36


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def load_geocode_cache():
    if GEOCODE_CACHE_FILE.is_file():
        try:
            return json.loads(GEOCODE_CACHE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_geocode_cache(cache):
    try:
        GEOCODE_CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True))
    except OSError:
        pass


def clean_location_for_geocoding(location):
    """Entfernt Zusaetze, die die Ortssuche in die Irre fuehren (z.B. 'i.d.R.'
    vor wechselnden Kursorten, oder Klammerzusaetze wie '(Annulliert)')."""
    text = re.sub(r"\bi\.d\.R\.?\s*", "", location, flags=re.IGNORECASE)
    text = re.sub(r"\([^)]*\)", "", text)
    return text.strip()


def geocode_location(location, region, cache):
    """Ungefaehre Koordinaten fuer einen Ortsnamen via geo.admin.ch, mit
    Region als Plausibilitaetscheck gegen falsche Treffer (z.B. gleichnamige
    Orte in anderen Kantonen). Ergebnis wird im uebergebenen cache-dict
    gecacht (persistieren via save_geocode_cache obliegt dem Aufrufer)."""
    centroid = REGION_CENTROID.get(region)
    if not location or not centroid:
        return None, None

    cache_key = f"{region}|{location}"
    if cache_key in cache:
        cached = cache[cache_key]
        return tuple(cached) if cached else (None, None)

    clat, clon, max_km = centroid
    query = clean_location_for_geocoding(location)
    if not query:
        cache[cache_key] = None
        return None, None

    result = (None, None)
    try:
        url = f"{GEOCODE_URL}?{urllib.parse.urlencode({'searchText': query, 'type': 'locations', 'limit': 5})}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ol-termine-viewer)"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for item in data.get("results", []):
            attrs = item.get("attrs", {})
            lat, lon = attrs.get("lat"), attrs.get("lon")
            if lat is None or lon is None:
                continue
            if haversine_km(clat, clon, lat, lon) <= max_km:
                result = (lat, lon)
                break
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError):
        pass

    cache[cache_key] = list(result) if result[0] is not None else None
    return result


def parse_coords(mapurl):
    m = re.search(r"map\.search\.ch/([\-\d.]+),([\-\d.]+)", mapurl)
    if not m:
        return None, None
    e, n = float(m.group(1)), float(m.group(2))
    # Vereinzelt steht in der Quelle faelschlicherweise WGS84*1e6 statt LV03.
    if e > 900000 or n > 900000:
        return e / 1e6, n / 1e6
    return lv03_to_wgs84(e, n)


def parse_line(line, year):
    m = LINE_RE.search(line)
    if not m:
        return None

    rest = m.group("rest").strip()
    parts = re.split(r" {2,}", rest) if rest else []
    organizer = parts[0].strip() if len(parts) > 0 else ""
    location = parts[1].strip() if len(parts) > 1 else ""
    tail = parts[2] if len(parts) > 2 else ""

    href_m = re.search(r'<a href="([^"]+)"', tail)
    mapurl = href_m.group(1) if href_m else ""
    tail_clean = re.sub(r"<a[^>]*>.*?</a>", "", tail).strip()

    distance = ""
    icon = ""
    for tok in tail_clean.split():
        if tok in ("S", "M", "L"):
            distance = tok
        else:
            icon = tok

    lat, lon = parse_coords(mapurl) if mapurl else (None, None)
    uid = m.group("uid")

    return {
        "uid": uid,
        "date": f"{year}-{m.group('month')}-{m.group('day')}",
        "weekday": m.group("weekday"),
        "region": m.group("region"),
        "code": m.group("code") or "",
        "name": m.group("name").strip(),
        "organizer": organizer,
        "location": location,
        "distance": distance,
        "terrain": TERRAIN_BY_ICON.get(icon, "unbekannt"),
        "lat": lat,
        "lon": lon,
        "coord_source": "exact" if lat is not None else None,
        "detail_url": DETAIL_URL.format(uid=uid),
    }


def fetch_fixtures(year, geocode=True):
    """Holt und parst die Terminliste fuer ein Jahr. Wenn geocode=True,
    werden Termine ohne Koordinaten zusaetzlich ueber geo.admin.ch
    geschaetzt (siehe geocode_location) und der Cache auf Disk aktualisiert."""
    req = urllib.request.Request(
        f"{SOURCE_URL}?year={year}",
        headers={"User-Agent": "Mozilla/5.0 (ol-termine-viewer)"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("iso-8859-1")

    pre_m = re.search(r"<pre>(.*?)</pre>", raw, re.S)
    if not pre_m:
        return []

    events = []
    for line in pre_m.group(1).split("\n"):
        if not line.strip() or "cmsauth" in line:
            continue
        decoded = html.unescape(line)
        event = parse_line(decoded, year)
        if event:
            events.append(event)

    if geocode:
        cache = load_geocode_cache()
        cache_dirty = False
        for event in events:
            if event["lat"] is None:
                before = len(cache)
                lat, lon = geocode_location(event["location"], event["region"], cache)
                if len(cache) != before:
                    cache_dirty = True
                if lat is not None:
                    event["lat"], event["lon"], event["coord_source"] = lat, lon, "approx"
        if cache_dirty:
            save_geocode_cache(cache)

    return events
