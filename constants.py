from pathlib import Path

PROJEKT_DIR = Path(__file__).parent
CACHE_DIR = PROJEKT_DIR / ".cache"
VERSICHERER_DATEI = PROJEKT_DIR / "versicherer.json"

# Datenquelle: BAG-Prämiendaten über opendata.swiss.
#
# Bis zum Prämienjahr 2026 lag die Datei unter
# priminfo.admin.ch/downloads/gesamtbericht_ch.xlsx. Mit der Umstellung auf 2027
# wurde dieser Pfad abgeschaltet (404); priminfo verweist für die maschinen-
# lesbaren Daten nur noch auf opendata.swiss. Der Pfad im Query-String ist
# base64-kodiert und entspricht "/Praemien/Prämien_CH.xlsx".
#
# Die URL lässt sich jederzeit über die CKAN-Schnittstelle nachschlagen:
#   https://opendata.swiss/api/3/action/package_show?id=health-insurance-premiums
praemien_url = (
    "https://opendata.bagnet.ch/?r=/download"
    "&path=L1ByYWVtaWVuL1Byw6RtaWVuX0NILnhsc3g%3D"
)

# Die neue Datei führt genau ein Blatt, und es heisst "Sheet1" statt wie früher
# "Export". Ist der Name nicht vorhanden, nimmt lade_praemien das erste Blatt -
# eine weitere Umbenennung soll die App nicht lahmlegen.
praemien_sheet = "Sheet1"

# Rückerstattung der Umweltabgaben, pro Person und Monat. Sie wird von der Prämie
# abgezogen und ändert jedes Jahr (JEDES JAHR NEU!!!).
#
#   2027: 57.00 CHF pro Jahr = 4.75 pro Monat
#   2026: 61.80 CHF pro Jahr = 5.15 pro Monat
#
# Auf den Kipppunkt wirkt sich der Wert nicht aus - er entlastet jede Franchise
# gleich und lässt die Reihenfolge unverändert. Er bestimmt aber sämtliche
# absoluten Frankenbeträge.
umweltabgabe_standard = 57.00 / 12

# Gesetzliche Selbstbehalt-Obergrenze pro Jahr (Art. 103 KVV)
hoechstgrenze_selbstbehalt = {
    "Erwachsene": 700,
    "Jugendliche": 700,
    "Kinder": 350,
}

# Anteil der Kosten über der Franchise, den die versicherte Person trägt
selbstbehalt_anteil = 0.1

# Maximale jährliche Krankheitskosten für die Kipppunktanalyse
maximale_krankenkosten = 10000

ALTERSKLASSEN = {
    "AKL-ERW": "Erwachsene",
    "AKL-JUG": "Jugendliche",
    "AKL-KIN": "Kinder",
}

# Altersuntergruppen der Kinder. Nicht offiziell dokumentiert; K1 ist der Normalfall,
# K3/K5 sind Familienrabatte für weitere Kinder. Empirisch bewährt: K1 + K4.
KINDER_UNTERGRUPPEN_STANDARD = ("K1", "K4")

# Tariftypen ab Prämienjahr 2027. Das ist keine blosse Umbenennung: Bis 2026 gab
# es TAR-BASE, TAR-HAM, TAR-HMO und TAR-DIV, jetzt sind es fünf anders
# geschnittene Kategorien (laut "Erläuterungen zu den Prämiendaten" des BAG).
# Eine Zuordnung alt -> neu wäre geraten und unterbleibt deshalb.
TARIFTYPEN = {
    "BASE": "Standardmodell (freie Arztwahl)",
    "PRAXIS": "Praxis- und Hausarztmodelle",
    "FLEX": "Flexible Modelle",
    "TEL_DIG": "Telemedizin und digitale Modelle",
    "PHARM": "Apothekenmodelle",
}

REGIONEN = {
    "PR-REG CH0": "Region 0",
    "PR-REG CH1": "Region 1",
    "PR-REG CH2": "Region 2",
    "PR-REG CH3": "Region 3",
}

# Standardauswahl für den CLI-Lauf
kanton_standard = "ZH"
region_standard = "PR-REG CH1"
