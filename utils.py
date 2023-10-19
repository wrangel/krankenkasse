###import matplotlib.pyplot as plt
import pandas as pd

from constants import *


def get_praemienregion(text):
    """Berechne Prämienregion

    :param text: Parsed text from website
    :return: "Prämienregion" in String format
    """
    relevant_line = [line for line in text[text.index(praemienregion_marker_1):].split(line_splitter)
                     if all(item in line for item in praemienregion_marker_3)][0]
    return list(set([i.strip() for i in relevant_line.split(" ")]) - set(praemienregion_marker_3))[0]


def get_franchisen(text, praemienregion_marker):
    """Stelle die Franchisen zusammen.
    Erhalte Prämien für Erwachsene und Kinder
    Sortiere den Output: Zuerst die Kinder

    :param text: Parsed text from website
    :param praemienregion_marker: Marker for finding "Prämienregion" in the text
    :return: Dict with "Prämien" per "Zielgruppe", number of "Prämien"
    """
    praemien_1 = sorted(
        set([line for line in text.split(line_splitter) if praemienregion_marker in line])
        , key=lambda x: x[0])
    praemien_2 = [i[:i.find(praemienregion_marker_2)].strip().split(" ") for i in praemien_1]
    return {zielgruppen[0]: praemien_2[0], zielgruppen[1]: praemien_2[1]}, sum([len(l) for l in praemien_2]) - 1


def create_dict_entry(strings, numbers, versicherungsmodell):
    """ Creates a String with relevant infos accompanying "Prämien"

    :param strings: Components for info string
    :param numbers: "Prämien"
    :param versicherungsmodell: Type of insurance
    :return: String displaying all relevant info
    """
    return {versicherungsmodell + " - " + " ".join(strings).replace(", ", " - "): numbers}


def update_dict(info_und_praemien, strings, numbers, zielgruppe_id, versicherungsmodell):
    """ Den Prämien- und Info-Dict updaten

    :param info_und_praemien: Existing dict
    :param strings: Infos to add to the dict
    :param numbers: "Prämien" to add to the dict
    :param zielgruppe_id: Id of "Zielgruppe"
    :param versicherungsmodell: Name of "Versicherungsmodell
    :return: Updated dict
    """
    if zielgruppe_id == 1:
        # Ohne Unfall für Erwachsene
        relevant_numbers = numbers[praemien_split_index:]
    else:
        # Mit Unfall für Kinder
        relevant_numbers = numbers[:praemien_split_index]
    info_und_praemien[zielgruppen[zielgruppe_id]].update(
        create_dict_entry(strings, relevant_numbers, versicherungsmodell))


def handle_line(line, info_und_praemien, anzahl_praemien, zielgruppe_id, versicherungsmodell, umweltabgabe):
    numbers = []
    strings = []
    for s in line.split():
        try:
            a = float(s) - umweltabgabe
            numbers.append(float(s) - umweltabgabe)
        except ValueError:
            strings.append(s)
    if len(numbers) == anzahl_praemien:
        update_dict(info_und_praemien, strings, numbers, zielgruppe_id, versicherungsmodell)
    if len(numbers) == anzahl_praemien + 1:  # Entferne numerische Elemente in der Versicherungsbezeichnung
        strings.append(str(numbers[6]))
        del numbers[6]
        update_dict(info_und_praemien, strings, numbers, zielgruppe_id, versicherungsmodell)


def get_relevant_info(text, anzahl_franchisen, praemienregion_marker, unerwuenschte_angebote, umweltabgabe):
    # Instantiiere die Dicts für Erwachsene und Kinder
    info_und_praemien = {zielgruppe: {} for zielgruppe in zielgruppen}
    # Teile den Text in die einzelnen Prämienregionen auf
    for block in text.split(versicherungsmodell_marker):
        versicherungsmodell = block.split("\n")[0].strip()
        for zielgruppe_id in range(len(zielgruppen)):
            # Nimm nacheinander Erwachsene und Kinder, nimm die relevante Prämienregion
            if zielgruppe_marker[zielgruppe_id] in block and praemienregion_marker in block:
                for line in block.split(line_splitter):
                    # Schliesse Zeilen mit der Franchise, viel-Kind-Angebote und unerwünschte Angebote aus
                    if praemienregion_marker not in line and viel_kind_marker not in line \
                            and all(angebot not in line for angebot in unerwuenschte_angebote):
                        handle_line(line, info_und_praemien, anzahl_franchisen, zielgruppe_id, versicherungsmodell, umweltabgabe)
    return info_und_praemien


def get_beste_angebote(info_und_praemien, alle_franchisen):
    beste_praemien_pro_franchisen = []
    beste_praemien_pro_franchisen_dict = {zielgruppe: {} for zielgruppe in zielgruppen}
    for zielgruppe_id in range(len(zielgruppen)):
        relevant_dict = info_und_praemien[zielgruppen[zielgruppe_id]]
        info_liste = []
        praemien_liste = []
        [(info_liste.append(key),
          praemien_liste.append(relevant_dict[key]))
         for key in relevant_dict
         ]
        praemien_df = pd.DataFrame(praemien_liste).astype(float)
        for i in range(praemien_split_index):
            relevante_praemien = praemien_df[i]
            idx_minimale_praemie = relevante_praemien.idxmin()
            franchise = alle_franchisen[zielgruppen[zielgruppe_id]][i]
            praemie = relevante_praemien[idx_minimale_praemie]
            beste_praemien_pro_franchisen.append(
                (zielgruppen[zielgruppe_id], franchise, info_liste[idx_minimale_praemie], praemie))
            beste_praemien_pro_franchisen_dict[zielgruppen[zielgruppe_id]].update({int(franchise): praemie})
    [print(e) for e in beste_praemien_pro_franchisen]
    return beste_praemien_pro_franchisen_dict


def berechne_gesamtkosten(zielgruppe, beste_praemien_pro_franchisen, maximale_krankenkosten,
                          hoechstgrenze_selbstbehalt):
    franchisen_praemien = beste_praemien_pro_franchisen[zielgruppe]
    krankenkosten_jahr = [i for i in range(maximale_krankenkosten + 1)]
    gesamtkosten_jahr = pd.DataFrame(index=krankenkosten_jahr, columns=franchisen_praemien.keys())
    for franchise, praemie in franchisen_praemien.items():
        eigenkosten_jahr = []
        for i in krankenkosten_jahr:
            eigenkosten_jahr.append(
                # 12 * Monatsprämie
                12 * praemie \
                # falls die Krankheitskosten geringer sind als die Franchise,
                # zahle die Krankheitskosten, sonst zahle die gesamte Franchise
                + min(i, franchise) \
                # falls Krankheitskosten die Franchise übersteigen,
                # zahle 10% des übersteigenden Betrags, bis max. zur Höchstgrenze chf
                + min((max(0, i - franchise)) * 0.1, hoechstgrenze_selbstbehalt[zielgruppe])
            )
        gesamtkosten_jahr[franchise] = eigenkosten_jahr
    # Berechne die minimalen Gesamtkosten pro Krankheitskosten
    gesamtkosten_jahr['Min'] = gesamtkosten_jahr.idxmin(axis=1)
    # Ab welchen Krankenkosten lohnt sich die tiefe Franchise ?
    grenzwert = (gesamtkosten_jahr['Min'] - gesamtkosten_jahr['Min'].shift()).fillna(0).idxmin(axis=0)
    return gesamtkosten_jahr, grenzwert


def produce_results(zielgruppe, gesamtkosten_jahr, grenzwert, file_name):
    # Zeige, welche Franchise sich zu welchen Krankheitskosten lohnt
    ###plt.plot(gesamtkosten_jahr['Min'])
    ###plt.suptitle("Ab " + str(
    ###   grenzwert) + " CHF Krankheitskosten pro Jahr lohnt sich die tiefste Franchise für " + zielgruppe + ".",
    ###             fontsize=12)
    print("\n")
    with pd.option_context('display.max_rows', None, 'display.max_columns', None):
        print(gesamtkosten_jahr._slice(slice(grenzwert - 3, grenzwert + 3)))
    gesamtkosten_jahr.to_csv(file_name, sep='\t')
    ###plt.show()
