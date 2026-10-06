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
    mindest_rechenbereich,
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


_ALTERSKLASSEN_AB_2027: dict[str, str] = {
    "AKA_01_KIN": "AKL-KIN",
    "AKA_02_JUG": "AKL-JUG",
    "AKA_03_ERW": "AKL-ERW",
}

_UNFALL_AB_2027: dict[str, str] = {
    "MIT_UNF": "MIT-UNF",
    "OHN_UNF": "OHN-UNF",
}


def _normalisiere_codes(df: pd.DataFrame) -> pd.DataFrame:
    """Übersetzt die Schlüssel der Prämiendatei in die hausinterne Schreibweise.

    Mit dem Prämienjahr 2027 hat das BAG sämtliche Codes umgestellt:

        Region            PR-REG CH1  ->  PR_REG_1
        Altersklasse      AKL-ERW     ->  AKA_03_ERW
        Unfalleinschluss  OHN-UNF     ->  OHN_UNF
        Franchise         FRA-300     ->  FRA_01_E_0300   (neu mit Altersklasse)

    Statt die neue Schreibweise durch das ganze Projekt zu ziehen, wird sie hier
    einmal auf die bisherige zurückgeführt. Der Rest des Codes - und mit ihm die
    Tests - spricht damit weiterhin eine einzige Sprache. Dateien in der alten
    Schreibweise laufen unverändert durch.
    """
    df = df.copy()

    if "Altersklasse" in df:
        df["Altersklasse"] = df["Altersklasse"].replace(_ALTERSKLASSEN_AB_2027)
    if "Unfalleinschluss" in df:
        df["Unfalleinschluss"] = df["Unfalleinschluss"].replace(_UNFALL_AB_2027)

    # PR_REG_1 -> PR-REG CH1
    if "Region" in df:
        df["Region"] = df["Region"].str.replace(
            r"^PR_REG_(\d+)$", r"PR-REG CH\1", regex=True
        )

    # FRA_01_E_0300 -> FRA-300 (führende Nullen weg, Altersklassen-Buchstabe
    # entfällt - die Altersklasse steht ohnehin in einer eigenen Spalte)
    if "Franchise" in df:
        neu = df["Franchise"].str.extract(r"^FRA_\d+_[EJK]_(\d+)$")[0]
        df["Franchise"] = neu.where(neu.isna(), "FRA-" + neu.str.lstrip("0").replace("", "0")).fillna(
            df["Franchise"]
        )

    return df


def lade_praemien(max_alter_tage: int = 7) -> pd.DataFrame:
    """Rohe BAG-Prämientabelle. Der Download ist rund 14 MB und wird gecacht."""
    pfad = lade_datei(praemien_url, "praemien_ch.xlsx", max_alter_tage)

    # Die Tabelle einmal eingelesen daneben ablegen. Das Herunterladen der 12 MB
    # dauert unter einer Sekunde; das Einlesen der 220'000 Zeilen aus dem
    # Excel-Format kostet dagegen rund sechs Sekunden auf einem flotten Rechner
    # und ein Vielfaches davon auf der Synology - es ist reine Rechenarbeit.
    # Aus der Zwischenablage gelesen sind es 0.01 Sekunden, also rund 600-mal
    # schneller.
    #
    # Zwischengespeichert wird bewusst die *rohe* Tabelle, nicht die bereinigte:
    # So wirken Änderungen an der Entdoppelung und an _normalisiere_codes sofort,
    # ohne dass jemand daran denken muss, den Zwischenstand wegzuwerfen.
    zwischen = pfad.with_suffix(".pkl")
    df = None
    if zwischen.exists() and zwischen.stat().st_mtime >= pfad.stat().st_mtime:
        try:
            df = pd.read_pickle(zwischen)
        except Exception:
            # Unlesbar, etwa nach einem Versionswechsel von pandas: wegwerfen und
            # neu einlesen. Es ist nur eine Zwischenablage.
            zwischen.unlink(missing_ok=True)
            df = None

    if df is None:
        # Das Blatt hiess schon "Export" und heisst jetzt "Sheet1". Fehlt der
        # erwartete Name, wird das erste Blatt genommen, statt abzustürzen.
        blaetter = pd.ExcelFile(pfad).sheet_names
        blatt = praemien_sheet if praemien_sheet in blaetter else blaetter[0]
        df = pd.read_excel(pfad, sheet_name=blatt)
        try:
            df.to_pickle(zwischen)
        except Exception:
            # Ohne Schreibrecht läuft es weiter, nur eben langsam.
            pass

    # Früher stand hier ein Filter auf isBaseP == 0. Das war für die Datei bis
    # 2026 richtig, weil die Standardtarife dort doppelt geführt wurden und die
    # 0-Zeilen der doppelfreien Tabelle entsprachen. Ab 2027 ist isBaseP ein
    # schlichtes Kennzeichen ("Tarif Base? 1 = Ja, 0 = Nein"), und es gibt gar
    # keine Duplikate mehr - derselbe Filter hätte also sämtliche Standardtarife
    # verworfen, ohne dass irgendwo ein Fehler aufgetreten wäre. Deshalb wird
    # jetzt über den fachlichen Schlüssel entdoppelt: bis 2026 entfernt das die
    # Dubletten, ab 2027 ist es wirkungslos.
    schluessel = [
        "Versicherer", "Kanton", "Region", "Altersklasse", "Altersuntergruppe",
        "Unfalleinschluss", "Tarif", "Franchise",
    ]
    df = df.drop_duplicates(subset=[s for s in schluessel if s in df.columns])

    return _normalisiere_codes(df)


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
        "Junge Erwachsene": "OHN-UNF",
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
        """Grösster Vorteil der tiefsten Franchise gegenüber der *nächstbesten* Stufe.

        Achtung, eng gefasst: das misst nur, wie knapp benachbarte Franchisenstufen
        beieinander liegen – nicht, wie viel die Franchisenwahl insgesamt ausmacht.
        Dafür ist `max_spannweite` zuständig, die typisch ein Vielfaches beträgt.
        """
        return float(self.vorteil_tiefste.max())

    @property
    def nie_optimal(self) -> list[int]:
        """Franchisen, die über den ganzen Kostenbereich nie die günstigste sind.

        Empirisch sind das bisher alle mittleren Stufen – geprüft über sämtliche
        Kanton/Region-Kombinationen und einzelne Versichererangebote. Das ist aber
        ein Befund aus den Daten, keine Rechtsfolge: Die Verordnung deckelt den
        Prämienrabatt nur (Art. 95 Abs. 2bis KVV), festgelegt wird er von den
        Versicherern selbst (Abs. 1bis). Da die Prämien jedes Jahr neu bestimmt
        werden, wird der Befund hier bei jedem Lauf neu berechnet statt angenommen.
        """
        gewinner = set(self.optimal)
        return [f for f in self.kosten.columns if f not in gewinner]

    @property
    def spannweite(self) -> pd.Series:
        """Differenz zwischen bester und schlechtester Franchise je Kostenbetrag –
        also der Preis eines Fehlgriffs bei bekannten Krankheitskosten."""
        return self.kosten.max(axis=1) - self.kosten.min(axis=1)

    @property
    def max_spannweite(self) -> float:
        """Grösster Unterschied zwischen bester und schlechtester Franchise. Das ist
        der eigentliche Einsatz der Franchisenwahl: Wer seine Krankheitskosten kennt,
        spart bis zu diesem Betrag pro Jahr gegenüber der schlechtesten Wahl."""
        return float(self.spannweite.max())

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
    max_kosten: int = mindest_rechenbereich,
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
        "Junge Erwachsene": "OHN-UNF",
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
        teile["Junge Erwachsene"] = (
            _preisreihe(basis, "AKL-JUG", unfalldeckung["Junge Erwachsene"], franchise_jugendliche)
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
                f"  Gegenüber der nächstbesten Stufe bringt sie höchstens "
                f"{e.max_vorteil:.0f} CHF pro Jahr – benachbarte Franchisen liegen eng "
                f"beieinander."
            )
            print(
                f"  Die Franchisenwahl als solche wiegt aber schwer: zwischen bester und "
                f"schlechtester Franchise liegen bis zu {e.max_spannweite:.0f} CHF pro "
                f"Jahr (bei {e.spannweite.idxmax()} CHF Krankheitskosten)."
            )
            print()
            von = max(0, e.kipppunkt - umgebung)
            bis = min(e.kosten.index[-1], e.kipppunkt + umgebung)
            print(e.kosten.loc[von:bis].round(2).to_markdown())

        print(f"\nOptimale Franchise nach Krankheitskosten ({e.zielgruppe}):")
        print(e.segmente.to_markdown(index=False))


# Die Stufen, deren Bedingungen aus der BAG-Tarifliste bekannt sind. Das
# Feldverzeichnis des BAG nennt zusätzlich "K2"; in den Daten kommt es landesweit
# nicht vor, und die Tarifliste beschreibt es nicht. Taucht es oder eine andere
# unbekannte Stufe künftig auf, darf sie nicht stillschweigend übergangen werden -
# sie könnte einen Rabatt tragen, den die Rechnung dann unterschlägt.
BEKANNTE_KINDERSTUFEN = frozenset({"K1", "K3", "K4", "K5"})


def unbekannte_kinderstufen(daten: pd.DataFrame) -> set[str]:
    """Kinder-Tarifstufen in den Daten, deren Bedingung nicht bekannt ist."""
    if "Altersuntergruppe" not in daten or "Altersklasse" not in daten:
        return set()
    kinder = daten[daten["Altersklasse"].isin(["AKL-KIN", "Kinder"])]
    vorhanden = set(kinder["Altersuntergruppe"].dropna())
    return {s for s in vorhanden if s not in BEKANNTE_KINDERSTUFEN}


def kinder_stufen_verteilung(anzahl_kinder: int, verfuegbar: set[str]) -> list[str]:
    """Welche Tarifstufe jedes Kind bekommt, bei `anzahl_kinder` Kindern am selben Ort.

    Die Bedeutung der Stufen steht in der Tarifliste des BAG (Tarife.xlsx,
    Kategorie ALT):

        K1  ohne zusätzlichen Rabatt
        K3  Rabatt ab dem 3. Kind
        K4  Rabatt ab dem 2. Kind, gültig für alle Kinder
        K5  Rabatt ab dem 3. Kind, gültig für alle Kinder

    Damit lässt sich die Zuteilung aus der Kinderzahl ableiten, statt sie zu
    erfragen. "Gültig für alle Kinder" heisst: Ist die Schwelle erreicht, gilt
    der Rabatt für sämtliche Kinder, nicht erst ab dem n-ten. Achtung, K4 meint
    das zweite Kind, nicht das vierte - die Ziffer ist eine Stufennummer.

    Gibt eine Liste mit einer Stufe je Kind zurück; die günstigste Variante
    wählt der Aufrufer, weil sie von den Prämien des Versicherers abhängt.
    """
    if anzahl_kinder <= 0:
        return []

    kandidaten: list[list[str]] = [["K1"] * anzahl_kinder]
    if "K4" in verfuegbar and anzahl_kinder >= 2:
        kandidaten.append(["K4"] * anzahl_kinder)
    if "K5" in verfuegbar and anzahl_kinder >= 3:
        kandidaten.append(["K5"] * anzahl_kinder)
    if "K3" in verfuegbar and anzahl_kinder >= 3:
        # Nur die Kinder ab dem dritten bekommen den Rabatt.
        kandidaten.append(["K1", "K1"] + ["K3"] * (anzahl_kinder - 2))
    return kandidaten


def guenstigste_kinder_kombination(
    praemie_je_stufe: dict[str, float], anzahl_kinder: int
) -> tuple[float, list[str]]:
    """Billigste zulässige Stufenverteilung für `anzahl_kinder` Kinder.

    `praemie_je_stufe` enthält die Monatsprämien eines Versicherers je Stufe.
    Zurück kommt die Monatssumme für alle Kinder und die zugehörige Verteilung.
    """
    if anzahl_kinder <= 0:
        return 0.0, []

    beste: tuple[float, list[str]] | None = None
    for verteilung in kinder_stufen_verteilung(anzahl_kinder, set(praemie_je_stufe)):
        if any(stufe not in praemie_je_stufe for stufe in verteilung):
            continue
        summe = sum(praemie_je_stufe[stufe] for stufe in verteilung)
        if beste is None or summe < beste[0]:
            beste = (summe, verteilung)
    return beste if beste else (0.0, [])


def _kind_jahreskosten(
    praemie: float, franchise: int, krankheitskosten: float, umweltabgabe: float
) -> float:
    """Gesamtkosten eines Kindes für ein Jahr: Prämie plus Kostenbeteiligung."""
    obergrenze = hoechstgrenze_selbstbehalt["Kinder"]
    selbstbehalt = min(
        max(0.0, krankheitskosten - franchise) * selbstbehalt_anteil, obergrenze
    )
    return (
        12 * (praemie - umweltabgabe)
        + min(krankheitskosten, franchise)
        + selbstbehalt
    )


def kinder_beim_gleichen_versicherer(
    daten: pd.DataFrame, kosten_je_kind: list[float], umweltabgabe: float
) -> dict | None:
    """Günstigstes Angebot, wenn alle Kinder beim gleichen Versicherer sind.

    Das ist die Bedingung für jeden Geschwisterrabatt. Die Tarifliste des BAG
    (Tarife.xlsx, Kategorie ALT) beschreibt vier Schemas, und zwar in allen vier
    Sprachfassungen gleichlautend:

        K1  ohne zusätzlichen Rabatt
        K3  Rabatt ab dem 3. Kind
        K4  Rabatt ab dem 2. Kind, gültig für alle Kinder
        K5  Rabatt ab dem 3. Kind, gültig für alle Kinder

    Der Zusatz "gültig für alle Kinder" steht bei K4 und K5, nicht bei K3. Zwei
    Kinder bekommen also mit K4 beide den Rabatt, auch das erste; bei K3 bekommen
    ihn erst das dritte und jedes weitere.

    Entscheidend für die Rechnung: Das sind vier Schemas, von denen die Familie
    eines wählt - kein Baukasten, aus dem sich jedes Kind das günstigste nimmt.
    K4 für ein Kind und K5 für ein anderes wäre keine Mischform, die es zu kaufen
    gibt. Deshalb wird über die Schemas iteriert und innerhalb eines Schemas nur
    noch die Franchise je Kind frei gewählt.

    `daten` muss bereits auf Kinder, Wohnort, Unfalldeckung und Tarifmodelle
    gefiltert sein.
    """
    anzahl = len(kosten_je_kind)
    if anzahl == 0 or daten.empty:
        return None

    # Eine Stufe, deren Bedingung wir nicht kennen, wird unten nicht
    # berücksichtigt. Das darf nicht unbemerkt bleiben.
    unbekannt = {
        s for s in set(daten["Altersuntergruppe"].dropna())
        if s not in BEKANNTE_KINDERSTUFEN
    }

    bestes: dict | None = None
    for (versicherer, tarif), gruppe in daten.groupby(
        ["Versicherername", "Tarifbezeichnung"]
    ):
        vorhanden = set(gruppe["Altersuntergruppe"].dropna())
        for schema in kinder_stufen_verteilung(anzahl, vorhanden):
            gesamt = 0.0
            aufteilung = []
            for stufe, krankheitskosten in zip(schema, kosten_je_kind):
                moeglich = gruppe[gruppe["Altersuntergruppe"] == stufe]
                if moeglich.empty:
                    aufteilung = []
                    break
                kosten = moeglich.apply(
                    lambda z: _kind_jahreskosten(
                        z["Prämie"], int(z["Franchise"]), krankheitskosten, umweltabgabe
                    ),
                    axis=1,
                )
                beste_zeile = moeglich.loc[kosten.idxmin()]
                gesamt += float(kosten.min())
                aufteilung.append(
                    {
                        "franchise": int(beste_zeile["Franchise"]),
                        "stufe": stufe,
                        "kosten": float(kosten.min()),
                    }
                )
            if not aufteilung:
                continue
            if bestes is None or gesamt < bestes["total"]:
                bestes = {
                    "versicherer": versicherer,
                    "tarif": tarif,
                    "total": gesamt,
                    "je_kind": aufteilung,
                    "schema": list(schema),
                }
    if bestes is not None:
        bestes["unbekannte_stufen"] = sorted(unbekannt)
    return bestes
