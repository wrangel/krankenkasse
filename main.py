from datetime import datetime
import pandas as pd
from utils import *
from tika import parser
import tika
import httplib2
from bs4 import BeautifulSoup

tika.initVM()

if __name__ == "__main__":

    # Get the metadata
    http = httplib2.Http()
    _, content = http.request(website + home)

    url_metadata = [website + link["href"] for link in BeautifulSoup(content, "html.parser").find_all(
        "a", href=True) if legende_link % datetime.now().year in link["href"]][0]

    metadata = pd.read_excel(url_metadata, sheet_name=legende_sheet_name, skiprows=1, usecols=relevant_columns[:2]).\
        replace("\\n", " ", regex=True).\
        rename(columns={relevant_columns[0]: relevant_columns[3],
               relevant_columns[1]: relevant_columns[2]})

    # Get the data
    data = pd.read_csv(
        download_url, encoding=download_url_encoding, delimiter=";", usecols=relevant_columns[3:] + filter_columns)

    # Filter and beautify the data
    filtered_data = data[

        # Prämienregion ZH Stadt
        (data[filter_columns[0]] == filter_prämienregion) &
        # Erwachsene ohne Unfall, Kinder mit Unfall
        (
            (
                (data[filter_columns[1]] == "AKL-ERW") &
                (data[filter_columns[3]] == "OHN-UNF")
            )
            |
            (
                (data[filter_columns[1]] == "AKL-KIN") &
                (data[filter_columns[3]] == "MIT-UNF")
            )
        ) &
        # Keine spezielle Altersuntergruppe (Drei-, Vier-, und Fünfkind-Tarife)
        (
            (data[filter_columns[2]].isna()) |
            (data[filter_columns[2]] == "K1")
        ) &
        # Nur Basistarife
        (data[filter_columns[4]] == 0)
    ]

    # Join the relevant data with metadata
    relevant_data = filtered_data.merge(metadata, on="Versicherer",
                                        how="left").iloc[:, [8, 7, 2, 5, 6]]

    # Finde beste Prämie pro Franchise

    print(relevant_data)

    a = relevant_data.groupby(
        ["Altersklasse", "Franchise"])["Prämie"].min()
    print(a)
    quit()

    '''

    print("Zielgruppe (Erwachsene oder Kinder):")
    zielgruppe = input()
    print("Umweltabgabe (pro Monat, findet man per Web-Suche):")
    umweltabgabe = float(input())
    '''

    zielgruppe = "Kinder"
    umweltabgabe = 5.35
    ###

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

    ##
    a = get_relevant_info(relevant_text, anzahl_franchisen, praemienregion_marker,
                          unerwuenschte_angebote, umweltabgabe)
    quit()
    ##

    beste_praemien_pro_franchisen = get_beste_angebote(
        get_relevant_info(relevant_text, anzahl_franchisen, praemienregion_marker,
                          unerwuenschte_angebote, umweltabgabe), alle_franchisen
    )

    kostenuebersicht, grenzwert = berechne_gesamtkosten(
        zielgruppe, beste_praemien_pro_franchisen, maximale_krankenkosten,
        hoechstgrenze_selbstbehalt
    )

    produce_results(zielgruppe, kostenuebersicht, grenzwert, output_file)
