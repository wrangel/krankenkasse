from datetime import datetime
import pandas as pd
from utils import *
from tika import parser
import tika
import httplib2
from bs4 import BeautifulSoup

tika.initVM()

if __name__ == "__main__":

    # Umweltabgabe
    print("Umweltabgabe (pro Monat, findet man per Web-Suche):")
    umweltabgabe = float(input())

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

    print(beste_prämie_pro_franchise)  # OUTPUT TODO

    beste_prämie_pro_franchise_dict = beste_prämie_pro_franchise.iloc[:, [
        0, 1, 2]].groupby("Altersklasse")\
        .apply(lambda x: x.set_index("Altersklasse").to_dict("list")).to_dict()

    # .to_dict('records')

    print(beste_prämie_pro_franchise_dict)

    quit()

    # - umweltabgabe TODO

    kostenuebersicht, grenzwert = berechne_gesamtkosten(
        zielgruppe, beste_praemien_pro_franchisen, maximale_krankenkosten,
        hoechstgrenze_selbstbehalt
    )

    produce_results(zielgruppe, kostenuebersicht, grenzwert, output_file)
