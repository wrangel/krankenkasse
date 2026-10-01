"""Prüft, ob sich die Datenquellen des BAG verändert haben.

Hintergrund: Die beiden Quellen brechen auf ganz unterschiedliche Weise.

* Die Prämiendatei liegt unter einem festen Pfad. Sie verschwindet nie – ihr
  Inhalt wird jährlich still ersetzt. Ein blosser Erreichbarkeitstest würde die
  Umstellung auf ein neues Prämienjahr also gar nicht bemerken.
* Das Versichererverzeichnis trägt Hash *und* Jahr im Pfad
  (``…/wKeV97535ICf/Zugelassene Krankenversicherer_1.1.2026.xlsx``) und läuft
  jedes Jahr auf einen 404.

Geprüft wird gegen den zuletzt festgehaltenen Stand in ``datenstand.json``.

Zwei Dinge werden dabei streng auseinandergehalten:

* **Handlungsbedarf an den Quellen** – tote URL, umbenannte Spalte, neues
  Prämienjahr, verändertes Kennzeichen. Das macht das Werkzeug kaputt oder
  verfälscht es still. Exit-Code 1, im Workflow eine fehlgeschlagene Prüfung.
* **Ein anderer Befund** – welche Franchisen je die günstigsten sind, wo der
  Kipppunkt liegt. Das ist *kein* Sollwert. Die Prämien werden jedes Jahr neu
  festgesetzt, und was sich lohnt, folgt aus ihnen; dass bisher nur die höchste
  und die tiefste Franchise gewonnen haben, ist eine Beobachtung über einzelne
  Jahre, keine Vorgabe. Ändert sie sich, hat nichts versagt – dann ist bloss die
  Beschreibung in README und Oberfläche veraltet. Die Prüfung bleibt grün, der
  Befund erscheint als Warnung und in der Zusammenfassung des Laufs.

``datenstand.json`` ist entsprechend ein Gedächtnis, kein Sollwert: Es hält fest,
was zuletzt beobachtet wurde, damit Veränderung überhaupt auffällt.

    python pruefe_datenquellen.py              # prüfen
    python pruefe_datenquellen.py --schreiben   # aktuellen Stand festhalten
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

from constants import praemien_url
from refresh_versicherer import VERZEICHNIS_URL
from utils import beste_praemien, berechne_kipppunkt, get_data, lade_praemien

STAND_DATEI = Path(__file__).parent / "datenstand.json"

# Der Stand oben wird bei jedem Festhalten überschrieben - er beschreibt immer nur
# das Jetzt. Die Historie daneben wird nur ergänzt: ein Eintrag pro Prämienjahr.
# So entsteht über die Jahre eine Reihe, an der sich die Beobachtung "nur die
# höchste und die tiefste Franchise gewinnen" tatsächlich prüfen lässt, statt sie
# aus der Erinnerung zu behaupten.
HISTORIE_DATEI = Path(__file__).parent / "befund_historie.json"
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

    return abweichungen


def befund_aenderungen(erwartet: dict, gefunden: dict) -> list[str]:
    """Was die Daten heute anders erzählen als beim letzten Festhalten.

    Bewusst getrennt von `vergleiche`: Dort geht es um Dinge, die das Werkzeug
    kaputt machen – eine tote URL, eine umbenannte Spalte, ein gekipptes
    Kennzeichen. Hier geht es um das Ergebnis der Rechnung selbst, und das ist
    kein Sollwert. Dass bisher nur die höchste und die tiefste Franchise je
    optimal waren, ist eine Beobachtung über die Prämien einzelner Jahre, keine
    Vorgabe, an der sich neue Daten zu messen hätten. Ändert sie sich, hat nicht
    die Rechnung versagt, sondern die Beschreibung in README und Oberfläche ist
    veraltet.
    """
    aenderungen: list[str] = []
    alt_befund = erwartet.get("befund_referenz", {})
    neu_befund = gefunden.get("befund_referenz", {})

    for zielgruppe in ("Erwachsene", "Kinder"):
        alt = alt_befund.get(zielgruppe)
        neu = neu_befund.get(zielgruppe)
        if not alt or not neu:
            continue
        if alt["optimal"] != neu["optimal"]:
            aenderungen.append(
                f"{zielgruppe}: Je günstigste Franchisen zuletzt {alt['optimal']}, "
                f"jetzt {neu['optimal']}."
            )
        if alt["kipppunkt"] != neu["kipppunkt"]:
            aenderungen.append(
                f"{zielgruppe}: Kipppunkt zuletzt {alt['kipppunkt']}, "
                f"jetzt {neu['kipppunkt']}."
            )

    return aenderungen


def historie_ergaenzen(gefunden: dict) -> tuple[list[dict], bool]:
    """Trägt den Befund des aktuellen Prämienjahres in die Historie ein.

    Pro Prämienjahr ein Eintrag. Ein bereits vorhandenes Jahr wird aktualisiert
    (etwa wenn mitten im Jahr nachkorrigiert wird), sonst hinten angefügt.
    Gibt die vollständige Reihe zurück und ob sie um ein Jahr gewachsen ist.
    """
    historie: list[dict] = []
    if HISTORIE_DATEI.exists():
        historie = json.loads(HISTORIE_DATEI.read_text(encoding="utf-8"))

    jahr = gefunden["praemienjahr"]
    eintrag = {
        "praemienjahr": jahr,
        "erfasst_am": date.today().isoformat(),
        "kanton": REFERENZ_KANTON,
        "region": REFERENZ_REGION,
    }
    for zielgruppe in ("Erwachsene", "Kinder"):
        befund = gefunden["befund_referenz"].get(zielgruppe)
        if befund:
            eintrag[zielgruppe] = {
                "optimal": befund["optimal"],
                "nie_optimal": befund["nie_optimal"],
                "kipppunkt": befund["kipppunkt"],
            }

    vorhanden = next((e for e in historie if e.get("praemienjahr") == jahr), None)
    neu = vorhanden is None
    if vorhanden is not None:
        historie[historie.index(vorhanden)] = eintrag
    else:
        historie.append(eintrag)
    historie.sort(key=lambda e: e.get("praemienjahr", 0))

    HISTORIE_DATEI.write_text(
        json.dumps(historie, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return historie, neu


def zeige_historie(historie: list[dict]) -> None:
    """Druckt die Reihe über alle erfassten Prämienjahre."""
    if not historie:
        return
    print(f"\nBefund über die erfassten Prämienjahre ({REFERENZ_KANTON} "
          f"{REFERENZ_REGION}):")
    print(f"  {'Jahr':<6} {'Erwachsene: optimal':<24} {'Kipp.':>6}   "
          f"{'Kinder: optimal':<18} {'Kipp.':>6}")
    for eintrag in historie:
        erw = eintrag.get("Erwachsene", {})
        kin = eintrag.get("Kinder", {})
        print(
            f"  {eintrag.get('praemienjahr', '?'):<6} "
            f"{str(erw.get('optimal', '-')):<24} {str(erw.get('kipppunkt', '-')):>6}   "
            f"{str(kin.get('optimal', '-')):<18} {str(kin.get('kipppunkt', '-')):>6}"
        )


def _melde_an_github(aenderungen: list[str], praemienjahr: int) -> None:
    """Hebt einen geänderten Befund im GitHub-Lauf hervor, ohne ihn scheitern zu lassen.

    Ein veränderter Befund ist kein Fehlschlag - die Prüfung bleibt grün. Er soll
    aber auch nicht im Protokoll untergehen, deshalb eine Warnungs-Annotation und
    ein Eintrag in der Zusammenfassung des Laufs.
    """
    if not os.environ.get("GITHUB_ACTIONS"):
        return

    for aenderung in aenderungen:
        print(f"::warning title=Befund geändert::{aenderung}")

    pfad = os.environ.get("GITHUB_STEP_SUMMARY")
    if not pfad:
        return
    with open(pfad, "a", encoding="utf-8") as datei:
        datei.write(f"### Befund Prämienjahr {praemienjahr}\n\n")
        datei.write(
            "Die Daten ergeben etwas anderes als beim letzten Festhalten. "
            "Das ist ein Befund, kein Fehler:\n\n"
        )
        for aenderung in aenderungen:
            datei.write(f"- {aenderung}\n")
        datei.write(
            "\nZu prüfen ist nur, ob die Beschreibung in README und Oberfläche "
            "noch zu den Daten passt.\n"
        )


def main() -> int:
    zerleger = argparse.ArgumentParser(description=__doc__)
    zerleger.add_argument(
        "--schreiben",
        action="store_true",
        help="Den aktuellen Zustand in datenstand.json festhalten.",
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

    # Ist eine Quelle nicht erreichbar, hier abbrechen. Vorher lief das Skript
    # trotzdem weiter, lud die Datei und endete in einem Traceback - der Befund
    # stand zwar oben im Protokoll, ging aber im Stapel unter.
    if probleme:
        print("\n" + "=" * 72)
        print("DATENQUELLE NICHT ERREICHBAR")
        print("=" * 72)
        for problem in probleme:
            print(f"\n* {problem}")
        print(
            "\nDie maschinenlesbaren Prämiendaten liegen auf opendata.swiss. Die "
            "aktuelle Download-Adresse liefert:\n"
            "    https://opendata.swiss/api/3/action/package_show"
            "?id=health-insurance-premiums\n"
            "Gesucht ist die Ressource /Praemien/Prämien_CH.xlsx; der Pfad steckt "
            "base64-kodiert im Query-String."
        )
        return 1

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
        historie, ist_neues_jahr = historie_ergaenzen(gefunden)
        print(f"\nStand in {STAND_DATEI.name} festgehalten.")
        if ist_neues_jahr:
            print(
                f"Prämienjahr {gefunden['praemienjahr']} neu in "
                f"{HISTORIE_DATEI.name} aufgenommen ({len(historie)} Jahre erfasst)."
            )
        else:
            print(f"Eintrag für {gefunden['praemienjahr']} in "
                  f"{HISTORIE_DATEI.name} aktualisiert.")
        zeige_historie(historie)
        return 0

    if not STAND_DATEI.exists():
        print(
            f"\n{STAND_DATEI.name} fehlt. Einmalig mit --schreiben anlegen.",
            file=sys.stderr,
        )
        return 1

    erwartet = json.loads(STAND_DATEI.read_text(encoding="utf-8"))
    probleme.extend(vergleiche(erwartet, gefunden))
    aenderungen = befund_aenderungen(erwartet, gefunden)

    # Zuerst das Ergebnis der Rechnung - es ist eine Beobachtung, kein Sollwert,
    # und steht deshalb für sich, unabhängig vom Ausgang der Prüfung.
    if aenderungen:
        _melde_an_github(aenderungen, gefunden["praemienjahr"])
        print("\n" + "-" * 72)
        print("DIE DATEN ERGEBEN ETWAS ANDERES ALS BEIM LETZTEN FESTHALTEN")
        print("-" * 72)
        for aenderung in aenderungen:
            print(f"  {aenderung}")
        print(
            "\n  Das ist ein Befund, kein Fehler: Die Prämien werden jedes Jahr neu\n"
            "  festgesetzt, und welche Franchisen sich lohnen, folgt aus ihnen - nicht\n"
            "  umgekehrt. Zu tun ist nur eines: nachsehen, ob die Beschreibung in\n"
            "  README und Oberfläche noch zu den Daten passt."
        )

    if not probleme:
        if not aenderungen:
            print("\nDatenquellen unverändert, Befund wie zuletzt festgehalten.")
        else:
            print("\nDatenquellen in Ordnung; der Befund hat sich geändert (siehe oben).")
        return 0

    print("\n" + "=" * 72)
    print("HANDLUNGSBEDARF AN DEN DATENQUELLEN")
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
