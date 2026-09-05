from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import json
import urllib.request

import numpy as np
import pandas as pd

from constants import (
    ALTERSKLASSEN,
    CACHE_DIR,
    KINDER_UNTERGRUPPEN_STANDARD,
    VERSICHERER_DATEI,
    hoechstgrenze_selbstbehalt,
    maximale_krankenkosten,
    praemien_sheet,
    praemien_url,
    selbstbehalt_anteil,
)

# admin.ch weist Anfragen ohne Browser-User-Agent ab.
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def lade_datei(url: str, dateiname: str, max_alter_tage: int = 7) -> Path:
    """Lädt eine Datei und legt sie im Cache ab. Ein vorhandener Download wird
    wiederverwendet, solange er jünger als `max_alter_tage` ist."""
    CACHE_DIR.mkdir(exist_ok=True)
    ziel = CACHE_DIR / dateiname

    if ziel.exists():
        alter = datetime.now() - datetime.fromtimestamp(ziel.stat().st_mtime)
        if alter < timedelta(days=max_alter_tage):
            return ziel

    anfrage = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    with urllib.request.urlopen(anfrage) as antwort:
        inhalt = antwort.read()

    temp = ziel.with_suffix(ziel.suffix + ".teil")
    temp.write_bytes(inhalt)
    temp.replace(ziel)
    return ziel


def versicherer_namen() -> dict[int, str]:
    """Zuordnung BAG-Nummer -> Versicherername (siehe refresh_versicherer.py)."""
    if not VERSICHERER_DATEI.exists():
        return {}
    roh = json.loads(VERSICHERER_DATEI.read_text(encoding="utf-8"))
    return {int(nummer): name for nummer, name in roh.items()}


def lade_praemien(max_alter_tage: int = 7) -> pd.DataFrame:
    """Rohe BAG-Prämientabelle. Der Download ist rund 14 MB und wird gecacht."""
    pfad = lade_datei(praemien_url, "gesamtbericht_ch.xlsx", max_alter_tage)
    df = pd.read_excel(pfad, sheet_name=praemien_sheet)

    # TAR-BASE-Zeilen sind doppelt vorhanden (isBaseP 0 und 1); 0 entspricht der
    # vollständigen, doppelfreien Tabelle über alle Tariftypen.
    return df[df["isBaseP"] == 0]


def get_data(
    df: pd.DataFrame,
    kanton: str = "ZH",
    region: str = "PR-REG CH1",
    zielgruppen: tuple[str, ...] = ("Erwachsene", "Kinder"),
    unfalldeckung: dict[str, str] | None = None,
    kinder_untergruppen: tuple[str, ...] = KINDER_UNTERGRUPPEN_STANDARD,
    tariftypen: tuple[str, ...] | None = None,
) -> pd.DataFrame:
    """Filtert die BAG-Prämiendaten auf Kanton, Region, Zielgruppen und Unfalldeckung
    und normalisiert Franchise, Prämie und Altersklasse."""
    unfalldeckung = unfalldeckung or {
        "Erwachsene": "OHN-UNF",
        "Jugendliche": "OHN-UNF",
        "Kinder": "MIT-UNF",
    }
    akl_pro_zielgruppe = {name: akl for akl, name in ALTERSKLASSEN.items()}

    basis = df[(df["Kanton"] == kanton) & (df["Region"] == region)]
    if tariftypen:
        basis = basis[basis["Tariftyp"].isin(tariftypen)]

    teile = []
    for zielgruppe in zielgruppen:
        akl = akl_pro_zielgruppe[zielgruppe]
        teil = basis[
            (basis["Altersklasse"] == akl)
            & (basis["Unfalleinschluss"] == unfalldeckung[zielgruppe])
        ]
        if zielgruppe == "Kinder" and kinder_untergruppen:
            teil = teil[teil["Altersuntergruppe"].isin(kinder_untergruppen)]
        teile.append(teil)

    gefiltert = pd.concat(teile) if teile else basis.iloc[0:0]

    ergebnis = gefiltert[
        [
            "Versicherer",
            "Altersklasse",
            "Altersuntergruppe",
            "Unfalleinschluss",
            "Tariftyp",
            "Franchise",
            "Prämie",
            "Tarifbezeichnung",
        ]
    ].copy()
    ergebnis["Franchise"] = (
        ergebnis["Franchise"].str.extract(r"FRA-(\d+)")[0].astype(int)
    )
    ergebnis["Prämie"] = ergebnis["Prämie"].astype(float)
    ergebnis["Zielgruppe"] = ergebnis["Altersklasse"].map(ALTERSKLASSEN)

    namen = versicherer_namen()
    ergebnis["Versicherername"] = (
        ergebnis["Versicherer"].map(namen).fillna(ergebnis["Versicherer"].astype(str))
    )
    return ergebnis


def beste_praemien(df: pd.DataFrame) -> pd.DataFrame:
    """Günstigstes Angebot pro Zielgruppe und Franchise, inklusive Anbieter."""
    if df.empty:
        return df
    idx = df.groupby(["Zielgruppe", "Franchise"])["Prämie"].idxmin()
    return (
        df.loc[idx]
        .sort_values(["Zielgruppe", "Franchise"])
        .reset_index(drop=True)
    )


@dataclass
class Ergebnis:
    zielgruppe: str
    praemien: dict[int, float]
    anbieter: dict[int, str]
    kosten: pd.DataFrame
    optimal: pd.Series
    segmente: pd.DataFrame
    kipppunkt: int | None
    tiefste_franchise: int
    ersparnis_am_kipppunkt: float | None = None

    @property
    def vorteil_tiefste(self) -> pd.Series:
        """Wie viel die tiefste Franchise pro Jahr besser ist als die beste Alternative.
        Negativ, solange sich eine höhere Franchise mehr lohnt."""
        andere = self.kosten.drop(columns=[self.tiefste_franchise])
        return andere.min(axis=1) - self.kosten[self.tiefste_franchise]

    @property
    def max_vorteil(self) -> float:
        """Grösster Vorteil der tiefsten Franchise gegenüber der besten Alternative,
        über den ganzen untersuchten Kostenbereich. In der Praxis erstaunlich klein:
        die Prämienrabatte pro Franchisenstufe sind so geregelt, dass sich die
        Varianten fast die Waage halten."""
        return float(self.vorteil_tiefste.max())

    def materieller_kipppunkt(self, toleranz: float = 50.0) -> int | None:
        """Erste Krankheitskosten, ab denen die tiefste Franchise um mehr als `toleranz`
        Franken pro Jahr besser ist.

        Der reine Kipppunkt ist mathematisch exakt, aber praktisch wertlos: die
        Kostenkurven schneiden sich sehr flach, deshalb geht es dort um Rappen. Erst
        dieser Wert beantwortet, ab wann sich der Wechsel spürbar lohnt.
        """
        treffer = self.vorteil_tiefste.index[self.vorteil_tiefste > toleranz]
        return int(treffer[0]) if len(treffer) else None


def _segmente(optimal: pd.Series) -> pd.DataFrame:
    """Fasst zusammenhängende Bereiche gleicher optimaler Franchise zusammen."""
    wechsel = optimal.ne(optimal.shift()).cumsum()
    gruppen = optimal.groupby(wechsel)
    return pd.DataFrame(
        {
            "Von": gruppen.apply(lambda g: g.index[0]).values,
            "Bis": gruppen.apply(lambda g: g.index[-1]).values,
            "Franchise": gruppen.first().values,
        }
    )


def berechne_kipppunkt(
    beste: pd.DataFrame,
    umweltabgabe: float,
    max_kosten: int = maximale_krankenkosten,
) -> list[Ergebnis]:
    """Berechnet für jede Zielgruppe die Jahreskosten je Franchise und daraus den
    Kipppunkt: die tiefsten Krankheitskosten, ab denen die tiefste Franchise gewinnt."""
    krankheitskosten = np.arange(max_kosten + 1)
    ergebnisse = []

    for zielgruppe, gruppe in beste.groupby("Zielgruppe"):
        praemien = dict(zip(gruppe["Franchise"], gruppe["Prämie"]))
        anbieter = dict(zip(gruppe["Franchise"], gruppe["Versicherername"]))
        obergrenze = hoechstgrenze_selbstbehalt[zielgruppe]

        kosten = pd.DataFrame(index=pd.Index(krankheitskosten, name="Krankheitskosten"))
        for franchise, praemie in sorted(praemien.items()):
            selbstbehalt = np.minimum(
                np.maximum(0, krankheitskosten - franchise) * selbstbehalt_anteil,
                obergrenze,
            )
            kosten[franchise] = (
                12 * (praemie - umweltabgabe)
                + np.minimum(krankheitskosten, franchise)
                + selbstbehalt
            )

        optimal = kosten.idxmin(axis=1)
        tiefste = min(praemien)
        treffer = optimal.index[optimal == tiefste]
        kipppunkt = int(treffer[0]) if len(treffer) else None

        ersparnis = None
        if kipppunkt is not None:
            zeile = kosten.loc[kipppunkt]
            andere = zeile.drop(index=tiefste)
            ersparnis = float(andere.min() - zeile[tiefste])

        ergebnisse.append(
            Ergebnis(
                zielgruppe=zielgruppe,
                praemien=praemien,
                anbieter=anbieter,
                kosten=kosten,
                optimal=optimal,
                segmente=_segmente(optimal),
                kipppunkt=kipppunkt,
                tiefste_franchise=tiefste,
                ersparnis_am_kipppunkt=ersparnis,
            )
        )
    return ergebnisse


@dataclass
class Haushalt:
    """Zusammensetzung eines Haushalts. `kinder` enthält pro Kind die
    Altersuntergruppe, wie sie der Versicherer für dieses Kind anwendet
    (z. B. ("K1", "K1", "K3") für drei Kinder, davon eines zum Rabatttarif)."""

    erwachsene: int = 1
    jugendliche: int = 0
    kinder: tuple[str, ...] = ()

    @property
    def anzahl_kinder(self) -> int:
        return len(self.kinder)


def _preisreihe(
    basis: pd.DataFrame,
    altersklasse: str,
    unfall: str,
    franchise: int,
    untergruppe: str | None = None,
) -> pd.Series:
    """Günstigste Prämie je (Versicherer, Tarifbezeichnung) für eine Personenkategorie."""
    teil = basis[
        (basis["Altersklasse"] == altersklasse)
        & (basis["Unfalleinschluss"] == unfall)
        & (basis["Franchise"] == f"FRA-{franchise}")
    ]
    if untergruppe is not None:
        teil = teil[teil["Altersuntergruppe"] == untergruppe]
    return teil.groupby(["Versicherer", "Tarifbezeichnung"])["Prämie"].min()


def haushalt_angebote(
    df: pd.DataFrame,
    haushalt: Haushalt,
    franchise_erwachsene: int = 300,
    franchise_jugendliche: int = 300,
    franchise_kinder: int = 0,
    kanton: str = "ZH",
    region: str = "PR-REG CH1",
    unfalldeckung: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Jahresprämie des ganzen Haushalts je Versicherer und Tarif, aufsteigend sortiert.

    Berücksichtigt werden nur Angebote, die *alle* benötigten Personenkategorien
    führen – inklusive der verlangten Kinder-Untergruppen. Das ist der ehrliche
    Vergleich für eine Familie: ein Versicherer mit günstigen Erwachsenenprämien,
    aber ohne Geschwisterrabatt, kann für den Haushalt teurer sein.
    """
    unfalldeckung = unfalldeckung or {
        "Erwachsene": "OHN-UNF",
        "Jugendliche": "OHN-UNF",
        "Kinder": "MIT-UNF",
    }
    basis = df[(df["Kanton"] == kanton) & (df["Region"] == region)]

    teile: dict[str, pd.Series] = {}
    if haushalt.erwachsene:
        teile["Erwachsene"] = (
            _preisreihe(basis, "AKL-ERW", unfalldeckung["Erwachsene"], franchise_erwachsene)
            * haushalt.erwachsene
        )
    if haushalt.jugendliche:
        teile["Jugendliche"] = (
            _preisreihe(basis, "AKL-JUG", unfalldeckung["Jugendliche"], franchise_jugendliche)
            * haushalt.jugendliche
        )
    for untergruppe in sorted(set(haushalt.kinder)):
        anzahl = haushalt.kinder.count(untergruppe)
        teile[f"Kinder {untergruppe}"] = (
            _preisreihe(
                basis, "AKL-KIN", unfalldeckung["Kinder"], franchise_kinder, untergruppe
            )
            * anzahl
        )

    if not teile:
        return pd.DataFrame()

    zusammen = pd.concat(teile, axis=1, join="inner").dropna()
    if zusammen.empty:
        return zusammen

    zusammen["Monatsprämie"] = zusammen.sum(axis=1)
    zusammen["Jahresprämie"] = zusammen["Monatsprämie"] * 12

    namen = versicherer_namen()
    ergebnis = zusammen.reset_index()
    ergebnis["Versicherername"] = (
        ergebnis["Versicherer"].map(namen).fillna(ergebnis["Versicherer"].astype(str))
    )
    return ergebnis.sort_values("Jahresprämie").reset_index(drop=True)


def kinder_kostenbeteiligung(
    kosten_je_kind: list[float], franchise: int
) -> tuple[float, bool]:
    """Kostenbeteiligung aller Kinder zusammen, mit Familien-Höchstgrenze.

    Art. 93 Abs. 3 KVV: Sind mehrere Kinder einer Familie beim gleichen Versicherer
    versichert, darf ihre Kostenbeteiligung das Zweifache des Höchstbetrages je Kind
    (Franchise plus Selbstbehalt-Obergrenze) nicht übersteigen.

    Gibt (Betrag, ob_gedeckelt) zurück. Die Verordnung setzt für unterschiedliche
    Franchisen der Kinder keine Formel fest ("so setzt der Versicherer die
    Höchstbeteiligung fest") – hier wird deshalb eine gemeinsame Franchise angenommen.
    """
    obergrenze = hoechstgrenze_selbstbehalt["Kinder"]
    einzeln = sum(
        min(k, franchise)
        + min(max(0.0, k - franchise) * selbstbehalt_anteil, obergrenze)
        for k in kosten_je_kind
    )
    hoechstbetrag = 2 * (franchise + obergrenze)
    return (min(einzeln, hoechstbetrag), einzeln > hoechstbetrag)


def display_results(
    ergebnisse: list[Ergebnis], umgebung: int = 3, toleranz: float = 50.0
) -> None:
    """Textausgabe für den CLI-Lauf."""
    for e in ergebnisse:
        if e.kipppunkt is None:
            print(
                f"\n{e.zielgruppe}: Die tiefste Franchise ({e.tiefste_franchise} CHF) "
                f"lohnt sich im untersuchten Bereich nie."
            )
        else:
            print(
                f"\nDie tiefste Franchise ({e.tiefste_franchise} CHF) bei {e.zielgruppe} "
                f"lohnt sich rechnerisch ab {e.kipppunkt} CHF Krankheitskosten."
            )
            spuerbar = e.materieller_kipppunkt(toleranz)
            if spuerbar is None:
                print(
                    f"  Aber: mehr als {toleranz:.0f} CHF pro Jahr bringt sie bis "
                    f"{e.kosten.index[-1]} CHF Krankheitskosten nie."
                )
            else:
                print(
                    f"  Spürbar (über {toleranz:.0f} CHF pro Jahr) wird der Vorteil "
                    f"erst ab {spuerbar} CHF."
                )
            print(
                f"  Grösster Vorteil überhaupt: {e.max_vorteil:.0f} CHF pro Jahr. "
                f"Die Wahl des Versicherers wiegt deutlich schwerer."
            )
            print()
            von = max(0, e.kipppunkt - umgebung)
            bis = min(e.kosten.index[-1], e.kipppunkt + umgebung)
            print(e.kosten.loc[von:bis].round(2).to_markdown())

        print(f"\nOptimale Franchise nach Krankheitskosten ({e.zielgruppe}):")
        print(e.segmente.to_markdown(index=False))
