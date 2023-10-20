# Ändert sich nie oder sehr selten:
# https://www.comparis.ch/krankenkassen/grundversicherungen/selbstbehalt
hoechstgrenze_selbstbehalt = {"Erwachsene": 700, "Kinder": 350}
maximale_krankenkosten = 10000

website = "https://www.bag.admin.ch"
home = "/bag/de/home/versicherungen/krankenversicherung/krankenversicherung-versicherer-aufsicht/verzeichnisse-krankenundrueckversicherer.html"
legende_link = "Zugelassene%%20Krankenversicherer_1.10.%s.xlsx"
legende_sheet_name = "Zugelassene Krankenversicherer"
relevant_columns = ["Nummer\nNuméro\nNumero", "Name\nNom\nNome", "Name des Versicherers", "Versicherer", "Altersklasse", "Unfalleinschluss",
                    "Franchise", "Prämie", "Tarifbezeichnung"]
filter_columns = ["Region", "Altersklasse",
                  "Altersuntergruppe", "Unfalleinschluss"]
filter_prämienregion = "PR-REG CH1"  # Zürich Stadt im Kanton Zürich

# alt

line_splitter = "\n\n"

# Stelle Textmarker zusammen
download_url = "https://bag-files.opendata.swiss/owncloud/index.php/s/83Vtexg1buoOk6M"
download_url_encoding = "iso-8859-1"
input_file = "https://www.priminfo.admin.ch/downloads/wegweiser_ZH.pdf"
text_marker_start = "Prämien – Grundversicherung\nPrimes – Assurance de base"
text_marker_end = "Prämienregionen\nRégions de primes"
zielgruppen = ["Kinder", "Erwachsene"]
zielgruppe_marker = ["Franchise " + zielgruppe for zielgruppe in zielgruppen]
viel_kind_marker = "dès le 3ème enfant"  # TODO deutsch Drei und mehr Kinder
unerwuenschte_angebote = ["Qualimed"]
versicherungsmodell_marker = "Prämien – "
praemien_split_index = 6
praemienregion_marker_1 = "Prämienregionen"
praemienregion_marker_2 = "Region / Région"
praemienregion_marker_3 = ["8057", "Zürich"]

output_file = "~/Desktop/uebersicht_krankenkasse.txt"
