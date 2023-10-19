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

    # Filter the data
    relevant_data = data[data[filter_columns[0]] == filter_prämienregion]

    print(relevant_data)
    quit()
    # Join the data with metadata
    a = data.merge(metadata, on="Versicherer", how="left")

    print(a)

    quit()

    '''
    print("!! ACHTUNG: Die Resultate bei Kindern sind nicht korrekt !!")

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
