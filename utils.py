from constants import *
import pandas as pd
import httplib2
from bs4 import BeautifulSoup
from datetime import datetime


def get_data():
    """
    Hole die Prämiendaten und bereite sie auf

    :return: Pandas DataFrame mit allen relevanten Daten
    """
    data = pd.read_csv(
        daten_url, encoding=daten_url_encoding, delimiter=";", usecols=relevant_columns[3:] + filter_columns)

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
    return filtered_data


def get_metadata():
    """
    Hole die Referenzdaten (Namen der Versicherer) und bereite sie auf

    :return: Pandas DataFrame mit allen relevanten Metadaten
    """
    http = httplib2.Http()
    _, content = http.request(website + legende_url)
    # Suche den Link
    url_metadata = [website + link["href"] for link in BeautifulSoup(content, "html.parser").find_all(
        "a", href=True) if legende_excel % datetime.now().year in link["href"]][0]
    # Hole die Daten vom Link
    metadata = pd.read_excel(url_metadata, sheet_name=legende_sheet_name, skiprows=1, usecols=relevant_columns[:2]).\
        replace("\\n", " ", regex=True).\
        rename(columns={relevant_columns[0]: relevant_columns[3],
               relevant_columns[1]: relevant_columns[2]})
    return metadata


def beste_prämien(relevant_data):
    """
    Finde beste Prämie pro Franchise

    :param relevant_data: Datensatz mit allen relevanten Informationen
    :return: Dict mit allen besten Prämien für jede Franchise, pro Zielgruppe
    """
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

    beste_prämie_pro_franchise_dict = list(
        beste_prämie_pro_franchise.iloc[:, [0, 1, 2]]
        .set_index("Franchise").groupby("Altersklasse").agg(dict).apply(lambda x: x.to_dict())
        .to_dict()
        .values()
    )[0]

    print("\n")
    print(beste_prämie_pro_franchise.to_markdown())
    return beste_prämie_pro_franchise_dict


def berechne_kipppunkt(beste_praemien_pro_franchisen, umweltabgabe):
    """Berechne die optimale Franchise pro Krankheitskosten

    :param beste_praemien_pro_franchisen: Dict mit besten Prämien pro Franchisen
    :param umweltabgabe: Abgefragte derzeitige Umweltabgabe
    :return: Liste von Tupeln mit Zielgruppe, Eigenkosten-Matrix und Kipppunkt der Krankheitskosten
    """
    results = []
    for zielgruppe, franchisen_praemien in beste_praemien_pro_franchisen.items():
        # Beziehe die Umweltabgaben mit ein (ohne Wirkung, da stets derselbe Abzug)
        franchisen_praemien.update((franchise, prämie-umweltabgabe)
                                   for franchise, prämie in franchisen_praemien.items())
        # Spanne einen Range an Krankenkosten auf
        krankenkosten_jahr = [i for i in range(maximale_krankenkosten + 1)]
        # Pivotiere Krankenosten und Franchisen
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
        results.append({"ZG": zielgruppe,
                       "GJ": gesamtkosten_jahr, "GW": grenzwert})
    return results


def display_results(results):
    """
    Zeige die Resultate an

    :param results: Resultate der Berechnung 
    """
    for result in results:
        with pd.option_context('display.max_rows', None, 'display.max_columns', None):
            print("\n")
            print(
                "Die tiefste Franchise bei %s lohnt sich ab jährlichen Krankheitskosten von %s CHF:" % (result["ZG"], result["GW"]))
            print("\n")
            print(result["GJ"]._slice(
                slice(result["GW"] - 3, result["GW"] + 3)).to_markdown())
    print("\n")
