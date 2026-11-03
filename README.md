# OL-Termine Viewer

Web-App, die die OL-Terminliste von [o-l.ch/cgi-bin/fixtures](https://o-l.ch/cgi-bin/fixtures) übersichtlicher darstellt: Liste mit Filter nach Wald-/Stadt-/Mix-OL, Google-Maps-Anzeige des Laufgebiets pro Termin, und ICS-Export für den Kalender.

Zwei Betriebsarten, gleiches Frontend (`index.html`/`app.js`/`style.css`):

- **Lokal** (`server.py`): holt die Daten live von o-l.ch, nur auf Klick ("Daten laden").
- **GitHub Pages** (statisch, kein eigener Server): ein täglicher GitHub-Actions-Workflow holt die Daten und committed sie als `data/fixtures-<jahr>.json`; das Frontend liest diese Dateien, wenn kein lokaler Server erreichbar ist.

## Lokal: Voraussetzungen

- Python 3 (keine zusätzlichen Pakete nötig, nur Standardbibliothek)

## Lokal: Starten

```
cd ~/projects/ol-termine
python3 server.py
```

Danach im Browser öffnen: [http://localhost:8765](http://localhost:8765)

Zum Beenden: `Ctrl+C` im Terminal.

## GitHub Pages: Einrichten

1. Repo auf GitHub pushen (bereits erledigt).
2. In den Repo-Settings unter **Pages** als Quelle "Deploy from a branch" → Branch `main`, Ordner `/ (root)` wählen.
3. Einmal manuell den Workflow anstossen, damit initiale Daten da sind: Tab **Actions** → "Update OL fixtures data" → **Run workflow**. Danach läuft er automatisch täglich (`.github/workflows/update-data.yml`) und aktualisiert `data/fixtures-<jahr>.json`.
4. Die Seite ist danach unter `https://<username>.github.io/<repo>/` erreichbar. Der "Daten laden"-Button zeigt dort automatisch den Stand der letzten Actions-Aktualisierung statt live von o-l.ch zu laden (kein Server zum Live-Abruf vorhanden).

`update_data.py` kann auch lokal manuell laufen, um `data/` ohne Warten auf den Cron-Job zu aktualisieren.

## JOM-Filter

Der Button "Nur JOM-Läufe" filtert anhand einer festen Liste von `unique_id`s in `jom-<jahr>.json` (z.B. `jom-2026.json`), da die JOM-Läufe nicht zuverlässig anhand von Region/Code erkennbar sind. Für ein neues Jahr diese Datei manuell anhand der aktuellen JOM-PDF von olvz.ch neu erstellen; ohne passende Datei ist der Button für das gewählte Jahr deaktiviert (Fehlermeldung im Status).

## Koordinaten ohne Angabe

Für Termine ohne Koordinaten von o-l.ch wird der Ortsname einmalig über den kostenlosen Schweizer Geodienst geo.admin.ch geschätzt (mit Region als Plausibilitätscheck gegen falsche Treffer). Ergebnisse landen in `geocode-cache.json` (versioniert, damit GitHub Actions nicht bei jedem Lauf neu anfragen muss) und werden bei künftigen Ladevorgängen wiederverwendet. Solche geschätzten Positionen sind in der Karte als "≈" gekennzeichnet.
