import pandas as pd
from utils import (
    get_data,
    beste_prämien,
    berechne_kipppunkt,
    display_results
)
import sys

if __name__ == "__main__":
    print("Umweltabgabe (pro Monat, findet man per Web-Suche):")
    umweltabgabe = 5.15  # TODO float(input())

    data = get_data(kanton="ZH", region="PR-REG CH1")

    beste_prämien_dict = beste_prämien(data)

    results = berechne_kipppunkt(beste_prämien_dict, umweltabgabe)
    display_results(results)
