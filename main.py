from datetime import datetime
import pandas as pd
from utils import *
from tika import parser
import tika
import httplib2
from bs4 import BeautifulSoup
from tabulate import tabulate

tika.initVM()

if __name__ == "__main__":

    beste_praemien_pro_franchisen = {'Erwachsene': {300: 444.6, 500: 433.7, 1000: 406.6, 1500: 379.5, 2000: 352.3, 2500: 324.8},
                                     'Kinder': {0: 104.5, 100: 99.4, 200: 94.3, 300: 89.1, 400: 84.3, 500: 78.9, 600: 73.7}}

    for zielgruppe, franchisen_praemien in beste_praemien_pro_franchisen.items():
        krankenkosten_jahr = [i for i in range(maximale_krankenkosten + 1)]
        gesamtkosten_jahr = pd.DataFrame(
            index=krankenkosten_jahr, columns=franchisen_praemien.keys())
        for franchise, praemie in franchisen_praemien.items():
            eigenkosten_jahr = []
            for franchise, praemie in franchisen_praemien.items():
                eigenkosten_jahr = []
                for i in krankenkosten_jahr:
                    eigenkosten_jahr.append(
                        # 12 * Monatsprämie
                        12 * praemie \
                        # falls die Krankheitskosten geringer sind als die Franchise, zahle die Krankheitskosten,
                        # sonst zahle die gesamte Franchise
                        + min(i, franchise) \
                        # falls Krankheitskosten die Franchise übersteigen,
                        # zahle 10% des übersteigenden Betrags, bis max. zur Höchstgrenze chf
                        + min((max(0, i - franchise)) * 0.1,
                              hoechstgrenze_selbstbehalt[zielgruppe])
                    )
                gesamtkosten_jahr[franchise] = eigenkosten_jahr
        # Berechne die minimalen Gesamtkosten pro Krankheitskosten
        gesamtkosten_jahr['Min'] = gesamtkosten_jahr.idxmin(axis=1)
        # Ab welchen Krankenkosten lohnt sich die tiefe Franchise?
        grenzwert = (
            gesamtkosten_jahr['Min'] - gesamtkosten_jahr['Min'].shift()).fillna(0).idxmin(axis=0)
        print(grenzwert)

    quit()

    # - umweltabgabe TODO

    #############

    # Umweltabgabe
    # print("Umweltabgabe (pro Monat, findet man per Web-Suche):")
    # umweltabgabe = float(input()) # TODO
    umweltabgabe = 5.35

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
        # Kanton ZH
        (data[filter_columns[5]] == "ZH") &
        # Prämienregion ZH Stadt
        (data[filter_columns[0]] == "PR-REG CH1") &
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
    relevant_data = filtered_data.merge(metadata, on="Versicherer", how="left")

    # Finde beste Prämie pro Franchise
    beste_prämie_pro_franchise_tmp1 = relevant_data.groupby(
        ["Altersklasse", "Franchise"]).agg(
            Prämie=("Prämie", "min")
    )

    beste_prämie_pro_franchise_tmp2 = beste_prämie_pro_franchise_tmp1\
        .merge(
            relevant_data, on=["Altersklasse", "Franchise", "Prämie"],
            how="left").iloc[:, [0, 1, 2, 10, 9]]\
        .replace("FRA-", "", regex=True)\
        .replace("AKL-ERW", "Erwachsene", regex=True)\
        .replace("AKL-KIN", "Kinder", regex=True)\
        .astype({"Franchise": int, "Prämie": float})

    beste_prämie_pro_franchise = beste_prämie_pro_franchise_tmp2.sort_values(
        by=["Altersklasse", "Franchise"])

    # print(beste_prämie_pro_franchise.to_markdown())  # OUTPUT TODO

    beste_prämie_pro_franchise_dict = list(
        beste_prämie_pro_franchise.iloc[:, [0, 1, 2]]
        .set_index("Franchise").groupby("Altersklasse").agg(dict).apply(lambda x: x.to_dict())
        .to_dict()
        .values()
    )[0]


'''
    kostenuebersicht, grenzwert = berechne_gesamtkosten(
        zielgruppe, beste_praemien_pro_franchisen, maximale_krankenkosten,
        hoechstgrenze_selbstbehalt
    )

    produce_results(zielgruppe, kostenuebersicht, grenzwert, output_file)
'''
