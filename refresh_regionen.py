"""Erzeugt die Zuordnung Postleitzahl -> Kanton und Prämienregion.

Die Prämienregion bestimmt die Prämie mit, aber kaum jemand weiss, in welcher
er wohnt. Gefragt wird deshalb nach der Postleitzahl, und die Region wird
nachgeschlagen.

Quelle ist die offizielle Regionenliste des BAG. Ihre URL trägt das Jahr
(``praemienregionen-2027.xlsx``) und ändert damit jährlich; die aktuelle steht
auf https://www.priminfo.admin.ch/de/downloads/aktuell

Achtung: Rund jede zwölfte Postleitzahl liegt in mehreren Regionen oder sogar
Kantonen – das BAG weist das in der Datei eigens aus. Die Zuordnung ist deshalb
eine Liste je PLZ, nicht ein einzelner Wert; die Oberfläche lässt in solchen
Fällen die Ortschaft wählen.

    python refresh_regionen.py
"""

from __future__ import annotations

import json

import pandas as pd

from constants import PROJEKT_DIR, REGIONEN_DATEI
from utils import lade_datei

REGIONEN_URL = "https://www.priminfo.admin.ch/downloads/praemienregionen-2027.xlsx"
BLATT = "B_NPA"
KOPFZEILE = 6


def hole_regionen() -> dict[str, list[dict]]:
    pfad = lade_datei(REGIONEN_URL, "praemienregionen.xlsx", max_alter_tage=0)
    roh = pd.read_excel(pfad, sheet_name=BLATT, header=KOPFZEILE)

    # Die Kopfzeilen sind zweisprachig und durch einen Zeilenumbruch getrennt
    # ("PLZ\nNPA"); hier interessiert nur der deutsche Teil.
    roh.columns = [str(s).split("\n")[0].strip() for s in roh.columns]
    roh = roh[["PLZ", "Ortsbezeichnung", "Kanton", "Region", "Gemeinde"]].dropna(
        subset=["PLZ", "Kanton", "Region"]
    )

    zuordnung: dict[str, list[dict]] = {}
    for _, zeile in roh.iterrows():
        plz = str(int(zeile["PLZ"]))
        eintrag = {
            "ort": str(zeile["Ortsbezeichnung"]).strip(),
            "kanton": str(zeile["Kanton"]).strip(),
            "region": int(zeile["Region"]),
            "gemeinde": str(zeile["Gemeinde"]).strip(),
        }
        bisher = zuordnung.setdefault(plz, [])
        # Mehrere Zeilen derselben PLZ unterscheiden sich oft nur in Details,
        # die für die Prämie nichts ändern. Entscheidend ist Kanton + Region.
        if not any(
            e["kanton"] == eintrag["kanton"] and e["region"] == eintrag["region"]
            and e["ort"] == eintrag["ort"]
            for e in bisher
        ):
            bisher.append(eintrag)

    return dict(sorted(zuordnung.items()))


def main() -> int:
    zuordnung = hole_regionen()
    REGIONEN_DATEI.write_text(
        json.dumps(zuordnung, indent=0, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    mehrdeutig = sum(
        1
        for eintraege in zuordnung.values()
        if len({(e["kanton"], e["region"]) for e in eintraege}) > 1
    )
    groesse = REGIONEN_DATEI.stat().st_size / 1024
    print(
        f"{len(zuordnung)} Postleitzahlen nach {REGIONEN_DATEI.name} geschrieben "
        f"({groesse:.0f} KB).\n"
        f"Davon {mehrdeutig} mit mehreren Kanton/Region-Kombinationen – dort fragt "
        f"die Oberfläche nach der Ortschaft."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
