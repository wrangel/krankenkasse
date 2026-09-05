from pathlib import Path

PROJEKT_DIR = Path(__file__).parent
CACHE_DIR = PROJEKT_DIR / ".cache"
VERSICHERER_DATEI = PROJEKT_DIR / "versicherer.json"

# Datenquelle: BAG Prämienvergleich
praemien_url = "https://www.priminfo.admin.ch/downloads/gesamtbericht_ch.xlsx"
praemien_sheet = "Export"

# Umweltabgabe pro Person und Monat, wird von der Prämie abgezogen (JEDES JAHR NEU!!!)
umweltabgabe_standard = 5.15

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

TARIFTYPEN = {
    "TAR-BASE": "Standardmodell",
    "TAR-HAM": "Hausarztmodell",
    "TAR-HMO": "HMO",
    "TAR-DIV": "Telmed / übrige",
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
