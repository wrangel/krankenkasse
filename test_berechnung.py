"""Rechentests mit erfundenen Prämien – ohne Netz, ohne BAG.

Wozu: Die CI prüft sonst nur, dass sich die Abhängigkeiten installieren lassen
und jedes Modul kompiliert. Die ganze App ist aber eine Rechenkette über pandas.
Änderte sich das Verhalten von ``groupby``, ``idxmin`` oder ``str.extract``, käme
klaglos ein falscher Kipppunkt heraus und die Prüfung bliebe grün. Diese Tests
schliessen genau diese Lücke – besonders für die monatlichen Dependabot-PRs.

Die Erwartungswerte sind von Hand gerechnet, nicht aus dem Code abgelesen. Sonst
würde der Test nur bestätigen, was das Programm ohnehin tut.

    python test_berechnung.py     # ohne pytest lauffähig
    pytest test_berechnung.py     # falls vorhanden, ebenfalls
"""

from __future__ import annotations

import pandas as pd

from utils import (
    beste_praemien,
    berechne_kipppunkt,
    get_data,
    kinder_kostenbeteiligung,
)

# --------------------------------------------------------------------------
# Erfundene Ausgangslage
#
# Erwachsene, Umweltabgabe 0, Selbstbehalt 10 % bis höchstens 700 CHF:
#
#     Kosten(f, k) = 12 · Prämie(f) + min(k, f) + min(max(0, k − f) · 0.1, 700)
#
# Mit Prämien 500.00 (F300) und 380.00 (F2500) gilt im Bereich 300 ≤ k < 2500:
#
#     Kosten(300, k) − Kosten(2500, k)
#       = 12·(500−380) + 300 + 0.1·(k−300) − k
#       = 1440 + 270 − 0.9·k
#
# Null wird das bei k = 1710 / 0.9 = 1900. Beide Varianten kosten dort exakt
# 6460.00 CHF. Franchise 1000 zu 460.00 ist so gewählt, dass sie nirgends
# gewinnt: bei tiefen Kosten schlägt sie die 2500er nicht, bei hohen die 300er.
# --------------------------------------------------------------------------

PRAEMIEN_ERWACHSENE = {300: 500.00, 1000: 460.00, 2500: 380.00}
ERWARTETER_KIPPPUNKT = 1900
KOSTEN_AM_KIPPPUNKT = 6460.00


def _rohdaten(praemien: dict[int, float], altersklasse: str = "AKL-ERW") -> pd.DataFrame:
    """Baut eine Tabelle in der Form, wie get_data sie erwartet."""
    return pd.DataFrame(
        [
            {
                "Kanton": "ZH",
                "Region": "PR-REG CH1",
                "Altersklasse": altersklasse,
                "Altersuntergruppe": None if altersklasse == "AKL-ERW" else "K1",
                "Unfalleinschluss": "OHN-UNF" if altersklasse == "AKL-ERW" else "MIT-UNF",
                "Tariftyp": "TAR-BASE",
                "Tarifbezeichnung": "Testtarif",
                "Versicherer": 8,
                "Franchise": f"FRA-{franchise}",
                "Prämie": praemie,
            }
            for franchise, praemie in praemien.items()
        ]
    )


def _ergebnis(praemien=None, umweltabgabe: float = 0.0, max_kosten: int = 10000):
    daten = get_data(
        _rohdaten(praemien or PRAEMIEN_ERWACHSENE), zielgruppen=("Erwachsene",)
    )
    return berechne_kipppunkt(beste_praemien(daten), umweltabgabe, max_kosten)[0]


def test_get_data_normalisiert_franchise_und_praemie():
    """FRA-300 muss zur Zahl 300 werden – hier hängt alles Weitere dran."""
    daten = get_data(_rohdaten(PRAEMIEN_ERWACHSENE), zielgruppen=("Erwachsene",))
    assert sorted(daten["Franchise"]) == [300, 1000, 2500]
    assert daten["Franchise"].dtype.kind == "i", "Franchise muss ganzzahlig sein"
    assert daten["Zielgruppe"].unique().tolist() == ["Erwachsene"]


def test_beste_praemien_nimmt_die_guenstigste_je_franchise():
    """Bei mehreren Angeboten je Franchise gewinnt das billigste."""
    # ignore_index, weil die echten Daten aus einem read_excel mit eindeutigem
    # Index kommen; beste_praemien greift mit .loc auf die Indexwerte zu.
    roh = pd.concat(
        [_rohdaten({300: 500.00}), _rohdaten({300: 444.00}), _rohdaten({2500: 380.00})],
        ignore_index=True,
    )
    beste = beste_praemien(get_data(roh, zielgruppen=("Erwachsene",)))
    praemie_300 = beste.loc[beste["Franchise"] == 300, "Prämie"].iloc[0]
    assert praemie_300 == 444.00


def test_kostenformel_stimmt_mit_handrechnung():
    """Stichproben gegen von Hand gerechnete Werte, inklusive Deckel von 700."""
    e = _ergebnis()
    # k = 0: nur Prämie
    assert e.kosten.loc[0, 300] == 12 * 500.00
    # k = 1900: 6000 + 300 Franchise + 160 Selbstbehalt
    assert e.kosten.loc[1900, 300] == KOSTEN_AM_KIPPPUNKT
    # k = 1900 bei F2500: 4560 + 1900, noch kein Selbstbehalt
    assert e.kosten.loc[1900, 2500] == KOSTEN_AM_KIPPPUNKT
    # k = 10000 bei F300: Selbstbehalt am Deckel (9700 · 0.1 > 700)
    assert e.kosten.loc[10000, 300] == 12 * 500.00 + 300 + 700


def test_kipppunkt_ist_der_handgerechnete_wert():
    e = _ergebnis()
    assert e.kipppunkt == ERWARTETER_KIPPPUNKT
    # Unmittelbar darunter muss die hohe Franchise gewinnen, darüber die tiefe.
    assert e.optimal.loc[ERWARTETER_KIPPPUNKT - 1] == 2500
    assert e.optimal.loc[ERWARTETER_KIPPPUNKT + 1] == 300


def test_mittlere_franchise_ist_nie_optimal():
    """Der zentrale Befund von README und Oberfläche."""
    e = _ergebnis()
    assert e.nie_optimal == [1000]
    assert sorted(set(e.optimal)) == [300, 2500]


def test_umweltabgabe_verschiebt_den_kipppunkt_nicht():
    """Sie entlastet jede Franchise gleich und lässt die Reihenfolge unberührt."""
    ohne = _ergebnis(umweltabgabe=0.0)
    mit = _ergebnis(umweltabgabe=12.50)
    assert ohne.kipppunkt == mit.kipppunkt
    # Die absoluten Kosten sinken dagegen um 12 · 12.50 = 150.
    assert ohne.kosten.loc[0, 300] - mit.kosten.loc[0, 300] == 150.0


def test_spannweite_und_vorteil_messen_verschiedenes():
    """max_vorteil vergleicht mit der nächstbesten Stufe, max_spannweite mit der
    schlechtesten – die Verwechslung war schon einmal eine falsche Aussage."""
    e = _ergebnis()
    assert e.max_spannweite > e.max_vorteil
    # Bei k = 0 ist F300 am teuersten, F2500 am günstigsten: 6000 − 4560.
    assert e.spannweite.loc[0] == 12 * 500.00 - 12 * 380.00


def test_familien_hoechstgrenze_nach_art_93_abs_3_kvv():
    """Mehrere Kinder beim gleichen Versicherer: höchstens 2 × (Franchise + 350)."""
    # Ein Kind, 5000 CHF Kosten, Franchise 600:
    # 600 + min(4400 · 0.1, 350) = 600 + 350 = 950, ungedeckelt.
    betrag, gedeckelt = kinder_kostenbeteiligung([5000.0], 600)
    assert (betrag, gedeckelt) == (950.0, False)

    # Zwei Kinder: 1900 – genau die Obergrenze, also noch nicht gedeckelt.
    betrag, gedeckelt = kinder_kostenbeteiligung([5000.0] * 2, 600)
    assert betrag == 1900.0 and not gedeckelt

    # Drei Kinder: 2850 ungedeckelt, gekappt auf 2 × (600 + 350) = 1900.
    betrag, gedeckelt = kinder_kostenbeteiligung([5000.0] * 3, 600)
    assert (betrag, gedeckelt) == (1900.0, True)


def test_kinder_haben_den_tieferen_selbstbehalt_deckel():
    """Für Kinder gilt 350 statt 700 (Art. 103 Abs. 2 KVV)."""
    daten = get_data(
        _rohdaten({0: 120.00, 600: 90.00}, altersklasse="AKL-KIN"),
        zielgruppen=("Kinder",),
    )
    e = berechne_kipppunkt(beste_praemien(daten), 0.0, 10000)[0]
    # k = 10000, Franchise 0: 12 · 120 + 0 + min(1000, 350) = 1440 + 350
    assert e.kosten.loc[10000, 0] == 12 * 120.00 + 350


def main() -> int:
    tests = [wert for name, wert in sorted(globals().items()) if name.startswith("test_")]
    fehler = 0
    for test in tests:
        try:
            test()
        except AssertionError as problem:
            fehler += 1
            print(f"FEHLGESCHLAGEN  {test.__name__}\n                {problem}")
        else:
            print(f"ok              {test.__name__}")
    print(f"\n{len(tests) - fehler} von {len(tests)} Tests bestanden.")
    return 1 if fehler else 0


if __name__ == "__main__":
    raise SystemExit(main())
