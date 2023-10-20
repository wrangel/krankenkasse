from constants import *
import pandas as pd


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
            print(result["GJ"]._slice(
                slice(result["GW"] - 3, result["GW"] + 3)).to_markdown())
            print("\n")
            print(
                "Die tiefste Franchise bei %s lohnt sich ab jährlichen Krankheitskosten von %s CHF" % (result["ZG"], result["GW"]))
    print("\n")
