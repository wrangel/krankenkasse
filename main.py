import pandas as pd
from utils import *
from tika import parser
import tika
from tabulate import tabulate

tika.initVM()

if __name__ == "__main__":

    # Umweltabgabe
    print("Umweltabgabe (pro Monat, findet man per Web-Suche):")
    umweltabgabe = float(input())

    # Bereite die Referenzdaten auf
    metadata = get_metadata()

    # Bereite die Prämiendaten auf
    data = get_data()

    # Join the relevant data with metadata
    relevant_data = data.merge(metadata, on="Versicherer", how="left")

    beste_prämie_pro_franchise_dict = beste_prämien(relevant_data)

    results = berechne_kipppunkt(beste_prämie_pro_franchise_dict, umweltabgabe)

    display_results(results)
