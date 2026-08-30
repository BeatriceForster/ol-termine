# OL-Termine Viewer

Lokale Web-App, die die OL-Terminliste von [o-l.ch/cgi-bin/fixtures](https://o-l.ch/cgi-bin/fixtures) übersichtlicher darstellt: Liste mit Filter nach Wald-/Stadt-/Mix-OL, Google-Maps-Anzeige des Laufgebiets pro Termin, und ICS-Export für den Kalender.

Die Daten werden nur auf Klick ("Daten laden") von o-l.ch geholt, nicht automatisch.

## Voraussetzungen

- Python 3 (keine zusätzlichen Pakete nötig, nur Standardbibliothek)

## Starten

```
cd ~/projects/ol-termine
python3 server.py
```

Danach im Browser öffnen: [http://localhost:8765](http://localhost:8765)

Zum Beenden: `Ctrl+C` im Terminal.
