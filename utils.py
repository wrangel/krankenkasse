import pandas as pd
from constants import praemien_url, praemien_sheet, hoechstgrenze_selbstbehalt, maximale_krankenkosten


def get_data(kanton="ZH", region="PR-REG CH1"):
    df = pd.read_excel(praemien_url, sheet_name=praemien_sheet)

    filtered = df[
        (df["Kanton"] == kanton) &
        (df["Region"] == region) &
        (df["Altersklasse"].isin(["AKL-ERW", "AKL-KIN"])) &
        (df["Unfalleinschluss"].isin(["OHN-UNF", "MIT-UNF"])) &
        ((df["Altersuntergruppe"].isna()) | (df["Altersuntergruppe"] == "K1")) &
        (df["isBaseP"] == 0)
    ]

    return filtered[["Versicherer", "Altersklasse", "Unfalleinschluss", "Franchise", "Prämie", "Tarifbezeichnung"]]


def beste_prämien(df):
    df = df.copy()
    df["Franchise"] = df["Franchise"].astype(int)
    df["Prämie"] = df["Prämie"].astype(float)
    df["Altersklasse"] = df["Altersklasse"].replace(
        {"AKL-ERW": "Erwachsene", "AKL-KIN": "Kinder"})

    grouped = df.groupby(["Altersklasse", "Franchise"]).agg(
        {"Prämie": "min"}).reset_index()
    merged = pd.merge(
        grouped, df, on=["Altersklasse", "Franchise", "Prämie"], how="left")

    print("\nBeste Prämien pro Franchise:")
    print(merged[["Altersklasse", "Franchise", "Prämie", "Versicherer"]].sort_values(
        ["Altersklasse", "Franchise"]).to_markdown())

    return merged.groupby("Altersklasse").apply(
        lambda g: dict(zip(g["Franchise"], g["Prämie"]))
    ).to_dict()


def berechne_kipppunkt(praemien_dict, umweltabgabe):
    results = []
    for zielgruppe, franchisen in praemien_dict.items():
        franchisen = {f: p - umweltabgabe for f, p in franchisen.items()}
        krankenkosten = list(range(maximale_krankenkosten + 1))
        kosten_df = pd.DataFrame(index=krankenkosten)

        for f, p in franchisen.items():
            kosten_df[f] = [
                12 * p + min(k, f) + min(max(0, k - f) * 0.1,
                                         hoechstgrenze_selbstbehalt[zielgruppe])
                for k in krankenkosten
            ]

        kosten_df["Min"] = kosten_df.idxmin(axis=1)
        grenzwert = (kosten_df["Min"] != kosten_df["Min"].shift()).idxmax()
        results.append({"ZG": zielgruppe, "GJ": kosten_df, "GW": grenzwert})
    return results


def display_results(results):
    for result in results:
        print(
            f"\nDie tiefste Franchise bei {result['ZG']} lohnt sich ab jährlichen Krankheitskosten von {result['GW']} CHF:\n")
        print(result["GJ"].loc[result["GW"]-3:result["GW"]+3].to_markdown())
