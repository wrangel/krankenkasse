import argparse

from constants import (
    kanton_standard,
    mindest_rechenbereich,
    region_standard,
    umweltabgabe_standard,
)
from utils import beste_praemien, berechne_kipppunkt, display_results, get_data, lade_praemien


def parse_args():
    p = argparse.ArgumentParser(
        description="Berechnet den Kipppunkt, ab dem sich die tiefste Franchise lohnt."
    )
    p.add_argument("--kanton", default=kanton_standard)
    p.add_argument("--region", default=region_standard)
    p.add_argument("--umweltabgabe", type=float, default=umweltabgabe_standard)
    p.add_argument("--max-kosten", type=int, default=mindest_rechenbereich)
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print("Berechne Kipppunkt basierend auf Umweltabgabe und BAG-Prämiendaten…")

    daten = get_data(lade_praemien(), kanton=args.kanton, region=args.region)
    beste = beste_praemien(daten)

    print("\nBeste Prämien pro Franchise:")
    print(
        beste[["Zielgruppe", "Franchise", "Prämie", "Versicherername", "Tarifbezeichnung"]]
        .to_markdown(index=False)
    )

    display_results(berechne_kipppunkt(beste, args.umweltabgabe, args.max_kosten))
