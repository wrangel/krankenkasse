import pandas as pd
from utils import (
    get_data,
    beste_prämien,
    berechne_kipppunkt,
    display_results
)
from constants import umweltabgabe_standard

if __name__ == "__main__":
    print("Berechne Kipppunkt basierend auf Umweltabgabe und BAG-Prämiendaten…")

    data = get_data(kanton="ZH", region="PR-REG CH1")
    beste_prämien_dict = beste_prämien(data)
    results = berechne_kipppunkt(beste_prämien_dict, umweltabgabe_standard)
    display_results(results)
