"""Erzeugt versicherer.json aus dem BAG-Verzeichnis der zugelassenen Krankenversicherer.

Die Download-URL enthält einen jährlich wechselnden Hash und muss von
https://www.bag.admin.ch/de/verzeichnisse-der-zugelassenen-kranken-und-rueckversicherer
abgelesen und unten eingetragen werden.

    python refresh_versicherer.py
"""

import json
import re
from pathlib import Path

import pandas as pd

from utils import lade_datei

VERZEICHNIS_URL = (
    "https://www.bag.admin.ch/dam/de/sd-web/wKeV97535ICf/"
    "Zugelassene%20Krankenversicherer_1.1.2026.xlsx"
)
SHEET = "Zugelassene Krankenversicherer"
ZIEL = Path(__file__).parent / "versicherer.json"


def _name(zelle) -> str:
    """Erste (deutsche) Zeile des mehrsprachigen Namensfeldes, Zeilenumbrüche nach
    Bindestrich zusammengefügt ("CSS Kranken-\\nVersicherung AG")."""
    zeilen = [z.strip() for z in str(zelle).split("\n") if z.strip()]
    if not zeilen:
        return ""
    name = zeilen[0]
    while name.endswith("-") and len(zeilen) > 1:
        zeilen.pop(0)
        name += zeilen[0]
    return re.sub(r"\s+", " ", name)


def main() -> None:
    pfad = lade_datei(VERZEICHNIS_URL, "zugelassene_krankenversicherer.xlsx", max_alter_tage=0)
    df = pd.read_excel(pfad, sheet_name=SHEET, header=None, skiprows=2)

    mapping = {}
    for _, zeile in df.iterrows():
        try:
            nummer = int(zeile[0])
        except (TypeError, ValueError):
            continue
        name = _name(zeile[2])
        if name and name != "nan":
            mapping[str(nummer)] = name

    ZIEL.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"{len(mapping)} Versicherer nach {ZIEL.name} geschrieben.")


if __name__ == "__main__":
    main()
