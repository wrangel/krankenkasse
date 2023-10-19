line_splitter = "\n\n"

# Ändert sich nie oder sehr selten:
# https://www.comparis.ch/krankenkassen/info/glossar/selbstbehalt-grundversicherung
hoechstgrenze_selbstbehalt = {"Erwachsene": 400, "Kinder": 350}
maximale_krankenkosten = 10000

# Stelle Textmarker zusammen
download_url = "https://bag-files.opendata.swiss/owncloud/index.php/s/83Vtexg1buoOk6M"
download_url_encoding = "iso-8859-1"
input_file = "https://www.priminfo.admin.ch/downloads/wegweiser_ZH.pdf"
text_marker_start = "Prämien – Grundversicherung\nPrimes – Assurance de base"
text_marker_end = "Prämienregionen\nRégions de primes"
zielgruppen = ["Kinder", "Erwachsene"]
zielgruppe_marker = ["Franchise " + zielgruppe for zielgruppe in zielgruppen]
viel_kind_marker = "dès le 3ème enfant"
unerwuenschte_angebote = ["Qualimed"]
versicherungsmodell_marker = "Prämien – "
praemien_split_index = 6
praemienregion_marker_1 = "Prämienregionen"
praemienregion_marker_2 = "Region / Région"
praemienregion_marker_3 = ["8057", "Zürich"]

output_file = "~/Desktop/uebersicht_krankenkasse.txt"
