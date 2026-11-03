#!/usr/bin/env python3
"""Lokaler Dev-Server fuer den OL-Termine-Viewer.

Holt die Terminliste von o-l.ch live auf Anfrage (Reload-Button in der
Web-Oberflaeche), parst sie und liefert sie als JSON. Fuer die oeffentliche
Version via GitHub Pages siehe update_data.py + .github/workflows/ stattdessen.
Ausschliesslich Python-Standardbibliothek, kein pip-Install noetig.

Start:  python3 server.py
Dann:   http://localhost:8765 im Browser oeffnen.
"""
import json
import re
import sys
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from fixtures_lib import fetch_fixtures

PORT = 8765
STATIC_DIR = Path(__file__).parent


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

        # Statische Dateien (index.html, style.css, app.js, data/*.json, ...)
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
            ".json": "application/json; charset=utf-8",
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
