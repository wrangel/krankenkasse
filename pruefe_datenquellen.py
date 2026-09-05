"""Prüft, ob sich die Datenquellen des BAG verändert haben.

Hintergrund: Die beiden Quellen brechen auf ganz unterschiedliche Weise.

* Die Prämiendatei liegt unter einem festen Pfad. Sie verschwindet nie – ihr
  Inhalt wird jährlich still ersetzt. Ein blosser Erreichbarkeitstest würde die
  Umstellung auf ein neues Prämienjahr also gar nicht bemerken.
* Das Versichererverzeichnis trägt Hash *und* Jahr im Pfad
  (``…/wKeV97535ICf/Zugelassene Krankenversicherer_1.1.2026.xlsx``) und läuft
  jedes Jahr auf einen 404.

Geprüft wird deshalb gegen den festgehaltenen Stand in ``datenstand.json``:
Erreichbarkeit, Prämienjahr, Spalten, Wertebereiche und der zentrale Befund
(nur die höchste und die tiefste Franchise sind je optimal). Weicht etwas ab,
endet das Skript mit Exit-Code 1 – im GitHub-Workflow wird daraus eine
fehlgeschlagene Prüfung samt Benachrichtigung.

    python pruefe_datenquellen.py              # prüfen
    python pruefe_datenquellen.py --schreiben   # aktuellen Stand festhalten
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

from constants import praemien_url
from refresh_versicherer import VERZEICHNIS_URL
from utils import beste_praemien, berechne_kipppunkt, get_data, lade_praemien

STAND_DATEI = Path(__file__).parent / "datenstand.json"
_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"

# Referenzauswahl für den Befundtest. Bewusst fix, damit der Vergleich über die
# Jahre denselben Ausschnitt betrifft.
REFERENZ_KANTON = "ZH"
REFERENZ_REGION = "PR-REG CH1"


def erreichbar(url: str) -> tuple[bool, str]:
    """Prüft eine URL, ohne die Datei herunterzuladen."""
    anfrage = urllib.request.Request(
        url, method="HEAD", headers={"User-Agent": _USER_AGENT}
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=60) as antwort:
            return True, f"HTTP {antwort.status}"
    except urllib.error.HTTPError as fehler:
        return False, f"HTTP {fehler.code}"
    except Exception as fehler:  # Netzwerk, DNS, TLS
        return False, f"{type(fehler).__name__}: {fehler}"


def aktueller_stand() -> dict:
    """Liest die Prämiendatei und beschreibt ihren heutigen Zustand."""
    roh = lade_praemien(max_alter_tage=0)
    daten = get_data(roh, kanton=REFERENZ_KANTON, region=REFERENZ_REGION)
    ergebnisse = berechne_kipppunkt(beste_praemien(daten), umweltabgabe=0.0)

    befund = {}
    for e in ergebnisse:
        befund[e.zielgruppe] = {
            "optimal": sorted(int(f) for f in set(e.optimal)),
            "nie_optimal": sorted(int(f) for f in e.nie_optimal),
            "kipppunkt": None if e.kipppunkt is None else int(e.kipppunkt),
        }

    return {
        "praemienjahr": int(roh["Geschäftsjahr"].max()),
        "spalten": sorted(str(s) for s in roh.columns),
        "altersklassen": sorted(str(a) for a in roh["Altersklasse"].dropna().unique()),
        "altersuntergruppen": sorted(
            str(u) for u in roh["Altersuntergruppe"].dropna().unique()
        ),
        "franchisen": sorted(str(f) for f in roh["Franchise"].dropna().unique()),
        "anzahl_kantone": int(roh["Kanton"].nunique()),
        "befund_referenz": {
            "kanton": REFERENZ_KANTON,
            "region": REFERENZ_REGION,
            **befund,
        },
    }


def vergleiche(erwartet: dict, gefunden: dict) -> list[str]:
    """Listet die Abweichungen als lesbare Meldungen auf."""
    abweichungen: list[str] = []

    if erwartet["praemienjahr"] != gefunden["praemienjahr"]:
        abweichungen.append(
            f"NEUES PRÄMIENJAHR: {erwartet['praemienjahr']} -> "
            f"{gefunden['praemienjahr']}. Die Umweltabgabe in constants.py gehört "
            f"überprüft, und versicherer.json muss über refresh_versicherer.py neu "
            f"geholt werden (neue URL mit neuem Hash)."
        )

    for feld, bezeichnung in [
        ("spalten", "Spalten der Prämiendatei"),
        ("altersklassen", "Altersklassen"),
        ("altersuntergruppen", "Altersuntergruppen der Kinder"),
        ("franchisen", "Franchisenstufen"),
    ]:
        fehlt = sorted(set(erwartet[feld]) - set(gefunden[feld]))
        neu = sorted(set(gefunden[feld]) - set(erwartet[feld]))
        if fehlt or neu:
            abweichungen.append(
                f"{bezeichnung} geändert – weggefallen: {fehlt or 'keine'}, "
                f"neu: {neu or 'keine'}."
            )

    alt_befund = erwartet.get("befund_referenz", {})
    neu_befund = gefunden.get("befund_referenz", {})
    for zielgruppe in ("Erwachsene", "Kinder"):
        alt = alt_befund.get(zielgruppe)
        neu = neu_befund.get(zielgruppe)
        if not alt or not neu:
            continue
        if alt["optimal"] != neu["optimal"]:
            abweichungen.append(
                f"BEFUND GEKIPPT ({zielgruppe}): Bisher waren nur die Franchisen "
                f"{alt['optimal']} je optimal, jetzt sind es {neu['optimal']}. Die "
                f"zentrale Aussage von README und Oberfläche stimmt so nicht mehr."
            )
        if not neu["nie_optimal"]:
            abweichungen.append(
                f"BEFUND GEKIPPT ({zielgruppe}): Es gibt keine dominierte Franchise "
                f"mehr – jede Stufe ist irgendwo die günstigste."
            )

    return abweichungen


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument(
        "--schreiben",
        action="store_true",
        help="Den aktuellen Zustand als neuen Sollstand in datenstand.json ablegen.",
    )
    argumente = zerleger.parse_args()

    print("Prüfe Erreichbarkeit der Datenquellen…")
    probleme: list[str] = []
    for name, url in [
        ("Prämienvergleich", praemien_url),
        ("Versichererverzeichnis", VERZEICHNIS_URL),
    ]:
        ok, meldung = erreichbar(url)
        print(f"  {'ok  ' if ok else 'FEHL'} {name}: {meldung}")
        if not ok:
            hinweis = ""
            if name == "Versichererverzeichnis":
                hinweis = (
                    " Erwartbar beim Jahreswechsel: Die URL enthält Hash und Jahr. "
                    "Neue URL auf bag.admin.ch ablesen und in refresh_versicherer.py "
                    "eintragen."
                )
            probleme.append(f"{name} nicht erreichbar ({meldung}).{hinweis}")

    print("\nLade Prämiendaten und ermittle den aktuellen Stand…")
    gefunden = aktueller_stand()
    print(f"  Prämienjahr: {gefunden['praemienjahr']}")
    print(f"  Altersuntergruppen: {', '.join(gefunden['altersuntergruppen'])}")
    for zielgruppe in ("Erwachsene", "Kinder"):
        eintrag = gefunden["befund_referenz"].get(zielgruppe)
        if eintrag:
            print(
                f"  {zielgruppe}: optimal {eintrag['optimal']}, "
                f"nie optimal {eintrag['nie_optimal']}, "
                f"Kipppunkt {eintrag['kipppunkt']}"
            )

    if argumente.schreiben:
        STAND_DATEI.write_text(
            json.dumps(gefunden, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(f"\nSollstand nach {STAND_DATEI.name} geschrieben.")
        return 0

    if not STAND_DATEI.exists():
        print(
            f"\n{STAND_DATEI.name} fehlt. Einmalig mit --schreiben anlegen.",
            file=sys.stderr,
        )
        return 1

    erwartet = json.loads(STAND_DATEI.read_text(encoding="utf-8"))
    probleme.extend(vergleiche(erwartet, gefunden))

    if not probleme:
        print("\nAlles unverändert gegenüber dem festgehaltenen Stand.")
        return 0

    print("\n" + "=" * 72)
    print("ABWEICHUNGEN GEFUNDEN")
    print("=" * 72)
    for problem in probleme:
        print(f"\n* {problem}")
    print(
        "\nNach dem Prüfen und Anpassen den neuen Stand festhalten:\n"
        "    python pruefe_datenquellen.py --schreiben"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
