from utils import *
from tika import parser
import tika

tika.initVM()

# TODO Angebote mit weniger als 12 Stufen gehen verloren; Problem bei Kindern!
# TODO display table in shell

# TODO 15% Rabatt auf Medikamente mit Pharmed

if __name__ == '__main__':

    import pandas as pd
    # https://opendata.swiss/de/dataset/health-insurance-premiums/resource/8cabe491-0280-41bb-ad31-e30bebabf985
    data = pd.read_csv(
        'https://bag-files.opendata.swiss/owncloud/index.php/s/83Vtexg1buoOk6M', encoding='iso-8859-1')

    print(
        "INPUTS:\n" +
        "https://www.finanzmonitor.com/krankenkasse/grundversicherung-krankenkasse-krankenkassenpramien-franchise-und-selbstbehalt/\n"
        "Weg dahin:\n"
        "\thttps://www.priminfo.admin.ch/de/praemien\n"
        "\tPrämienübersichten\n" +
        "\tZürich\n"
        "\tURL des PDF kopieren"
        "!! ACHTUNG: Angebote mit weniger als 12 Stufen gehen verloren, die Resultate bei Kindern sind daher nicht korrekt !!"
    )
    print("Zielgruppe (Erwachsene oder Kinder):")
    zielgruppe = input()
    print("Umweltabgabe (pro Monat, findet man per Web-Suche):")
    umweltabgabe = float(input())

    # Parse das PDF
    text = parser.from_file(input_file).get("content")

    # Berechne Prämienregion-Marker
    praemienregion_marker = praemienregion_marker_2 + \
        " " + get_praemienregion(text)

    # Stelle die Franchisen zusammen
    alle_franchisen, anzahl_franchisen = get_franchisen(
        text, praemienregion_marker)

    # Stelle die relevanten Informationen zusammen
    relevant_text = text[text.index(
        text_marker_start): text.index(text_marker_end)]

    beste_praemien_pro_franchisen = get_beste_angebote(
        get_relevant_info(relevant_text, anzahl_franchisen, praemienregion_marker,
                          unerwuenschte_angebote, umweltabgabe), alle_franchisen
    )

    kostenuebersicht, grenzwert = berechne_gesamtkosten(
        zielgruppe, beste_praemien_pro_franchisen, maximale_krankenkosten,
        hoechstgrenze_selbstbehalt
    )

    produce_results(zielgruppe, kostenuebersicht, grenzwert, output_file)
