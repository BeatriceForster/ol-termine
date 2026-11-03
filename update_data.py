#!/usr/bin/env python3
"""Generiert die statischen data/fixtures-<jahr>.json fuer GitHub Pages.

Wird vom GitHub-Actions-Workflow (.github/workflows/update-data.yml)
periodisch ausgefuehrt, kann aber auch lokal laufen:

    python3 update_data.py

Holt jeweils das Vorjahr bis zwei Jahre voraus (passend zur Jahresauswahl
im Frontend), parst und geocodiert, und schreibt die Ergebnisse nach data/.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fixtures_lib import fetch_fixtures

DATA_DIR = Path(__file__).parent / "data"


def main():
    DATA_DIR.mkdir(exist_ok=True)
    current_year = datetime.now().year
    years = range(current_year - 1, current_year + 3)
    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for year in years:
        print(f"Hole Termine {year} ...", file=sys.stderr)
        try:
            events = fetch_fixtures(year)
        except Exception as exc:  # noqa: BLE001 - ein Jahr soll die anderen nicht blockieren
            print(f"  Fehler bei {year}: {exc}", file=sys.stderr)
            continue

        payload = {
            "year": str(year),
            "count": len(events),
            "generated_at": generated_at,
            "events": events,
        }
        out_file = DATA_DIR / f"fixtures-{year}.json"
        out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        print(f"  {len(events)} Termine -> {out_file.name}", file=sys.stderr)


if __name__ == "__main__":
    main()
