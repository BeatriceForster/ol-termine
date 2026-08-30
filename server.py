#!/usr/bin/env python3
"""Lokaler Server fuer den OL-Termine-Viewer.

Holt die Terminliste von o-l.ch nur auf Anfrage (Reload-Button in der
Web-Oberflaeche), parst sie und liefert sie als JSON an die lokale
Web-Seite. Ausschliesslich Python-Standardbibliothek, kein pip-Install
noetig.

Start:  python3 server.py
Dann:   http://localhost:8765 im Browser oeffnen.
"""
import html
import json
import re
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

PORT = 8765
STATIC_DIR = Path(__file__).parent
SOURCE_URL = "https://o-l.ch/cgi-bin/fixtures"
DETAIL_URL = "https://o-l.ch/cgi-bin/fixtures?mode=show&unique_id={uid}"

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
        "detail_url": DETAIL_URL.format(uid=uid),
    }


def fetch_fixtures(year):
    req = urllib.request.Request(
        f"{SOURCE_URL}?year={year}",
        headers={"User-Agent": "Mozilla/5.0 (ol-termine-viewer local tool)"},
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
    return events


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write(f"{self.address_string()} - {fmt % args}\n")

    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/fixtures":
            qs = parse_qs(parsed.query)
            year = qs.get("year", ["2026"])[0]
            if not re.fullmatch(r"\d{4}", year):
                self.send_json({"error": "ungueltiges Jahr"}, status=400)
                return
            try:
                events = fetch_fixtures(year)
            except urllib.error.URLError as exc:
                self.send_json({"error": f"Abruf von o-l.ch fehlgeschlagen: {exc}"}, status=502)
                return
            self.send_json({"year": year, "count": len(events), "events": events})
            return

        # Statische Dateien (index.html, style.css, app.js)
        rel_path = parsed.path.lstrip("/") or "index.html"
        file_path = (STATIC_DIR / rel_path).resolve()
        if STATIC_DIR.resolve() not in file_path.parents and file_path != STATIC_DIR.resolve():
            self.send_error(403)
            return
        if not file_path.is_file():
            self.send_error(404)
            return

        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
        }.get(file_path.suffix, "application/octet-stream")

        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    server = ThreadingHTTPServer(("localhost", PORT), Handler)
    print(f"OL-Termine-Viewer laeuft auf http://localhost:{PORT}")
    print("Zum Beenden: Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
