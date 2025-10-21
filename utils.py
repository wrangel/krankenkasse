import pandas as pd
from constants import praemien_url, hoechstgrenze_selbstbehalt, maximale_krankenkosten


def get_data(kanton="ZH", region="PR-REG CH1"):
    """
    Lädt BAG-Prämiendaten und filtert nach Kanton, Region, Altersklasse und Unfalldeckung.
    Für Kinder werden alle Altersuntergruppen berücksichtigt, außer K1 und K2.
    """
    df = pd.read_excel(praemien_url, sheet_name="Export")

    filtered = df[
        (df["Kanton"] == kanton) &
        (df["Region"] == region) &
        (df["Altersklasse"].isin(["AKL-ERW", "AKL-KIN"])) &
        (
            ((df["Altersklasse"] == "AKL-ERW") & (df["Unfalleinschluss"] == "OHN-UNF")) |
            ((df["Altersklasse"] == "AKL-KIN") &
             (df["Unfalleinschluss"] == "MIT-UNF") &
             # Nicht dokumentiert, aber durch Versuche soweit als korrekt belegt
             (df["Altersuntergruppe"].isin(["K1", "K4"])))
        ) &
        (df["isBaseP"] == 0)
    ]

    return filtered[["Versicherer", "Altersklasse", "Unfalleinschluss", "Franchise", "Prämie", "Tarifbezeichnung"]]


def beste_prämien(df):
    """
    Ermittelt die günstigste Prämie pro Franchise und Altersklasse.
    Gibt ein Dictionary zurück: {Altersklasse: {Franchise: Prämie}}
    """
    df = df.copy()
    df["Franchise"] = df["Franchise"].str.extract(r"FRA-(\d+)")[0].astype(int)
    df["Prämie"] = df["Prämie"].astype(float)
    df["Altersklasse"] = df["Altersklasse"].replace(
        {"AKL-ERW": "Erwachsene", "AKL-KIN": "Kinder"}
    )

    grouped = df.groupby(["Altersklasse", "Franchise"]).agg(
        {"Prämie": "min"}).reset_index()
    merged = pd.merge(
        grouped, df, on=["Altersklasse", "Franchise", "Prämie"], how="left")

    print("\nBeste Prämien pro Franchise:")
    print(merged[["Altersklasse", "Franchise", "Prämie", "Versicherer"]]
          .sort_values(["Altersklasse", "Franchise"]).to_markdown())

    return {
        zielgruppe: dict(zip(gruppe["Franchise"], gruppe["Prämie"]))
        for zielgruppe, gruppe in merged.groupby("Altersklasse")
    }


def berechne_kipppunkt(praemien_dict, umweltabgabe):
    """
    Berechnet den Kipppunkt: ab welchen Krankheitskosten sich eine tiefere Franchise lohnt.
    Exportiert die Kostenmatrix als CSV.
    """
    results = []

    for zielgruppe, franchisen in praemien_dict.items():
        franchisen = {f: p - umweltabgabe for f, p in franchisen.items()}
        krankenkosten = list(range(maximale_krankenkosten + 1))
        kosten_df = pd.DataFrame(index=krankenkosten)

        for f, p in franchisen.items():
            kosten_df[f] = [
                12 * p + min(k, f) + min(
                    max(0, k - f) * 0.1,
                    hoechstgrenze_selbstbehalt[zielgruppe]
                )
                for k in krankenkosten
            ]

        kosten_df["Min"] = kosten_df.idxmin(axis=1)

        kipppunkt = next(
            (k for k in kosten_df.index[1:]
             if kosten_df["Min"].iloc[k] != kosten_df["Min"].iloc[k - 1]),
            None
        )

        results.append({"ZG": zielgruppe, "GJ": kosten_df, "GW": kipppunkt})
    return results


def display_results(results):
    """
    Zeigt den Kipppunkt und die Kostenmatrix im Bereich ±3 CHF um den Kipppunkt.
    """
    for result in results:
        print(
            f"\nDie tiefste Franchise bei {result['ZG']} lohnt sich ab jährlichen Krankheitskosten von {result['GW']} CHF:\n"
        )
        print(result["GJ"].loc[result["GW"] -
              3:result["GW"] + 3].to_markdown())
