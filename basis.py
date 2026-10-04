"""Grundbausteine: Daten laden, Zahlen formatieren, Wohnort und Altersklasse.

Alles, was mehrere Ansichten brauchen und was keine eigene Ansicht ist.
"""

import json

import pandas as pd
import streamlit as st

from constants import REGIONEN_DATEI
from utils import lade_praemien


@st.cache_data(show_spinner="Lade BAG-Prämiendaten…")
def praemien(max_alter_tage: int):
    return lade_praemien(max_alter_tage)


def chf(betrag: float, nachkomma: int = 0) -> str:
    return f"{betrag:,.{nachkomma}f}".replace(",", "'")


@st.cache_data
def regionen_nach_plz() -> dict[str, list[dict]]:
    """Postleitzahl -> mögliche Kanton/Region-Kombinationen (refresh_regionen.py)."""
    if not REGIONEN_DATEI.exists():
        return {}
    return json.loads(REGIONEN_DATEI.read_text(encoding="utf-8"))


def zielgruppe_fuer_alter(alter: int) -> str:
    """Altersklasse des BAG: Kinder bis 18, junge Erwachsene 19-25, danach Erwachsene."""
    if alter <= 18:
        return "Kinder"
    if alter <= 25:
        return "Jugendliche"
    return "Erwachsene"


def wohnort_waehlen(schluessel: int, spalte=None) -> tuple[str, str, str] | None:
    """Fragt die Postleitzahl ab und schlägt Kanton und Prämienregion nach.

    Die Prämienregion bestimmt die Prämie mit, aber kaum jemand weiss, in welcher
    er wohnt - die Postleitzahl weiss dagegen jeder. Rund jede zwölfte PLZ liegt
    allerdings in mehreren Regionen oder Kantonen; dann wird zusätzlich nach der
    Ortschaft gefragt, statt stillschweigend die erste zu nehmen.

    Gibt (Kanton, Region, Beschriftung) zurück oder None, wenn nichts passt.
    """
    ziel = spalte if spalte is not None else st
    zuordnung = regionen_nach_plz()
    if not zuordnung:
        ziel.error(
            "Die Zuordnung der Postleitzahlen fehlt. Einmalig erzeugen mit "
            "`python refresh_regionen.py`."
        )
        return None

    plz = ziel.text_input(
        "Postleitzahl", value="8001", max_chars=4, key=f"plz_{schluessel}"
    ).strip()
    eintraege = zuordnung.get(plz)
    if not eintraege:
        if plz:
            ziel.warning(f"Zur PLZ {plz} ist keine Prämienregion bekannt.")
        return None

    varianten = {(e["kanton"], e["region"]) for e in eintraege}
    if len(varianten) > 1:
        gewaehlt = ziel.selectbox(
            "Ortschaft",
            eintraege,
            format_func=lambda e: f"{e['ort']} ({e['kanton']}, Region {e['region']})",
            key=f"ort_{schluessel}",
            help="Diese Postleitzahl liegt in mehreren Prämienregionen.",
        )
    else:
        gewaehlt = eintraege[0]

    return (
        gewaehlt["kanton"],
        f"PR-REG CH{gewaehlt['region']}",
        f"{plz} {gewaehlt['ort']} ({gewaehlt['kanton']}, Region {gewaehlt['region']})",
    )


def mit_abstand(tabelle: pd.DataFrame, spalte: str, neue_spalte: str) -> pd.DataFrame:
    """Hängt rechts neben `spalte` den Abstand zum günstigsten Angebot an.

    Das günstigste bekommt 0, jedes weitere den Aufpreis gegenüber ihm. Erst das
    macht sichtbar, ob ein Rang ein Vorsprung ist oder eine Rundungsdifferenz.
    """
    werte = tabelle[spalte]
    tabelle.insert(
        tabelle.columns.get_loc(spalte) + 1,
        neue_spalte,
        (werte - werte.min()).round(2),
    )
    return tabelle

