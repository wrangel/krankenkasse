import json

import altair as alt
import pandas as pd
import streamlit as st

from constants import (
    KINDER_UNTERGRUPPEN,
    TARIFTYPEN_KURZ,
    REGIONEN_DATEI,
    TARIFTYPEN,
    maximale_krankenkosten,
    umweltabgabe_standard,
)
from utils import (
    Haushalt,
    beste_praemien,
    berechne_kipppunkt,
    get_data,
    haushalt_angebote,
    kinder_kostenbeteiligung,
    lade_praemien,
)

st.set_page_config(page_title="Welche Franchise lohnt sich?", page_icon="🏥", layout="wide")

FRANCHISEN_ERWACHSENE = [300, 500, 1000, 1500, 2000, 2500]
FRANCHISEN_KINDER = [0, 100, 200, 300, 400, 500, 600]



@st.cache_data(show_spinner="Lade BAG-Prämiendaten…")
def praemien(max_alter_tage: int):
    return lade_praemien(max_alter_tage)


def chf(betrag: float, nachkomma: int = 0) -> str:
    return f"{betrag:,.{nachkomma}f}".replace(",", "'")


@st.cache_data
def regionen_nach_plz() -> dict[str, list[dict]]:
    """Postleitzahl -> mögliche Kanton/Region-Kombinationen (refresh_regionen.py)."""
    if not REGIONEN_DATEI.exists():
        return {}
    return json.loads(REGIONEN_DATEI.read_text(encoding="utf-8"))


def zielgruppe_fuer_alter(alter: int) -> str:
    """Altersklasse des BAG: Kinder bis 18, junge Erwachsene 19-25, danach Erwachsene."""
    if alter <= 18:
        return "Kinder"
    if alter <= 25:
        return "Jugendliche"
    return "Erwachsene"


def wohnort_waehlen() -> tuple[str, str, str] | None:
    """Fragt die Postleitzahl ab und schlägt Kanton und Prämienregion nach.

    Die Prämienregion bestimmt die Prämie mit, aber kaum jemand weiss, in welcher
    er wohnt - die Postleitzahl weiss dagegen jeder. Rund jede zwölfte PLZ liegt
    allerdings in mehreren Regionen oder Kantonen; dann wird zusätzlich nach der
    Ortschaft gefragt, statt stillschweigend die erste zu nehmen.

    Gibt (Kanton, Region, Beschriftung) zurück oder None, wenn nichts passt.
    """
    zuordnung = regionen_nach_plz()
    if not zuordnung:
        st.error(
            "Die Zuordnung der Postleitzahlen fehlt. Einmalig erzeugen mit "
            "`python refresh_regionen.py`."
        )
        return None

    plz = st.text_input("Postleitzahl", value="8001", max_chars=4).strip()
    eintraege = zuordnung.get(plz)
    if not eintraege:
        if plz:
            st.warning(f"Zur Postleitzahl {plz} ist keine Prämienregion bekannt.")
        return None

    varianten = {(e["kanton"], e["region"]) for e in eintraege}
    if len(varianten) > 1:
        st.caption(
            f"Die Postleitzahl {plz} liegt in mehreren Prämienregionen – bitte die "
            f"Ortschaft wählen."
        )
        gewaehlt = st.selectbox(
            "Ortschaft",
            eintraege,
            format_func=lambda e: f"{e['ort']} ({e['kanton']}, Region {e['region']})",
        )
    else:
        gewaehlt = eintraege[0]
        orte = sorted({e["ort"] for e in eintraege})
        st.caption(
            f"{', '.join(orte[:3])}{' …' if len(orte) > 3 else ''} – "
            f"{gewaehlt['kanton']}, Prämienregion {gewaehlt['region']}"
        )

    return (
        gewaehlt["kanton"],
        f"PR-REG CH{gewaehlt['region']}",
        f"{plz} {gewaehlt['ort']} ({gewaehlt['kanton']}, Region {gewaehlt['region']})",
    )


def _mit_abstand(tabelle: pd.DataFrame, spalte: str, neue_spalte: str) -> pd.DataFrame:
    """Hängt rechts neben `spalte` den Abstand zum günstigsten Angebot an.

    Das günstigste bekommt 0, jedes weitere den Aufpreis gegenüber ihm. Erst das
    macht sichtbar, ob ein Rang ein Vorsprung ist oder eine Rundungsdifferenz.
    """
    werte = tabelle[spalte]
    tabelle.insert(
        tabelle.columns.get_loc(spalte) + 1,
        neue_spalte,
        (werte - werte.min()).round(2),
    )
    return tabelle


def einzelperson_ansicht(
    roh, kanton, region, ort_text, zielgruppe, unfalldeckung, tariftypen,
    kinder_untergruppen, umweltabgabe, erwartete_kosten,
):
    daten = get_data(
        roh,
        kanton=kanton,
        region=region,
        zielgruppen=(zielgruppe,),
        unfalldeckung=unfalldeckung,
        kinder_untergruppen=tuple(kinder_untergruppen),
        tariftypen=tuple(tariftypen) if tariftypen else None,
    )
    beste = beste_praemien(daten)
    if beste.empty:
        st.warning("Für diese Auswahl gibt es keine Prämien.")
        return

    # Gerechnet wird immer über einen Bereich, der die eingegebenen Kosten
    # einschliesst - sonst fiele ein hoher Wert aus der Kostenmatrix.
    rechenbereich = max(maximale_krankenkosten, int(erwartete_kosten) + 2000)
    ergebnisse = berechne_kipppunkt(beste, umweltabgabe, rechenbereich)
    if not ergebnisse:
        st.warning("Für diese Auswahl lässt sich nichts berechnen.")
        return
    e = ergebnisse[0]

    unfall_text = (
        "mit Unfalldeckung"
        if unfalldeckung.get(zielgruppe) == "MIT-UNF"
        else "ohne Unfalldeckung"
    )
    # Alle Eingaben einmal an einer Stelle. Danach müssen Überschriften und
    # Kennzahlen den Betrag nicht wiederholen.
    st.markdown(
        f"**{ort_text}** · {zielgruppe} · {unfall_text} · erwartete Krankheitskosten "
        f"**{chf(erwartete_kosten)} CHF pro Jahr**"
    )

    # Oben steht nur, was bei den angegebenen Kosten gilt. Der Kipppunkt selbst
    # erklärt die gestrichelte Linie im Diagramm und steht deshalb dort.
    bei_erwartung = e.kosten.loc[erwartete_kosten]
    beste_franchise = int(bei_erwartung.idxmin())
    links, rechts = st.columns(2)
    links.metric("Günstigste Franchise", f"{beste_franchise} CHF")
    rechts.metric("Gesamtkosten pro Jahr", f"{chf(bei_erwartung.min())} CHF")
    st.caption(
        "Prämien plus Franchise und Selbstbehalt, beim **günstigsten verfügbaren "
        "Angebot** – die Übersicht dazu steht weiter unten."
    )

    st.subheader("Kostenverlauf")
    kurven = e.kosten.reset_index().melt(
        id_vars="Krankheitskosten", var_name="Franchise", value_name="Jahreskosten"
    )
    dominiert = set(e.nie_optimal)
    kurven["Rolle"] = [
        "nie optimal" if f in dominiert else "kommt in Frage" for f in kurven["Franchise"]
    ]
    # Die bei den aktuellen Kosten günstigste Franchise wird fett gezeichnet - so
    # sieht man auf einen Blick, welche Kurve gerade die eigene ist.
    kurven["Auswahl"] = [
        "günstigste Wahl" if f == beste_franchise else "andere"
        for f in kurven["Franchise"]
    ]
    kurven["Franchise"] = kurven["Franchise"].astype(str)

    # Ausschnitt statt ganzer Bereich: Gezeigt wird die Umgebung der beiden
    # senkrechten Linien. Ein fester Rand nur um die eigenen Kosten würde den
    # Kipppunkt aus dem Bild schieben, sobald beide weit auseinander liegen -
    # und damit genau die Orientierung nehmen, die er geben soll.
    rand = 2000
    bezugspunkte = [erwartete_kosten] + (
        [e.kipppunkt] if e.kipppunkt is not None else []
    )
    fenster_von = max(0, min(bezugspunkte) - rand)
    fenster_bis = min(rechenbereich, max(bezugspunkte) + rand)
    kurven = kurven[
        kurven["Krankheitskosten"].between(fenster_von, fenster_bis)
    ]

    diagramm = (
        alt.Chart(kurven)
        .mark_line()
        .encode(
            x=alt.X("Krankheitskosten:Q", title="Jährliche Krankheitskosten (CHF)"),
            y=alt.Y(
                "Jahreskosten:Q",
                title="Gesamtkosten pro Jahr (CHF)",
                scale=alt.Scale(zero=False),
            ),
            color=alt.Color("Franchise:N", sort=None, title="Franchise"),
            strokeWidth=alt.StrokeWidth(
                "Auswahl:N",
                scale=alt.Scale(domain=["günstigste Wahl", "andere"], range=[4, 1.5]),
                legend=alt.Legend(title="bei deinen Kosten"),
            ),
            opacity=alt.Opacity(
                "Rolle:N",
                scale=alt.Scale(domain=["kommt in Frage", "nie optimal"], range=[1.0, 0.3]),
                legend=None,
            ),
            tooltip=[
                "Krankheitskosten",
                "Franchise",
                alt.Tooltip("Jahreskosten", format=".2f"),
                "Rolle",
            ],
        )
        .properties(height=360)
    )
    if e.kipppunkt is not None:
        diagramm += (
            alt.Chart(pd.DataFrame({"k": [e.kipppunkt]}))
            .mark_rule(strokeDash=[6, 4], color="#9aa0a6", size=2)
            .encode(x="k:Q")
        )
    hier = pd.DataFrame({"k": [erwartete_kosten], "beschriftung": ["du bist hier"]})
    diagramm += (
        alt.Chart(hier).mark_rule(color="#ff4b4b", size=3).encode(x="k:Q")
    )
    diagramm += (
        alt.Chart(hier)
        .mark_text(
            align="left", dx=6, dy=-6, baseline="top", color="#ff4b4b",
            fontSize=12, fontWeight="bold",
        )
        .encode(x="k:Q", y=alt.value(0), text="beschriftung:N")
    )

    # Klick ins Diagramm verschiebt die graue Linie. Der Regler in der Seitenleiste
    # bleibt die zweite Möglichkeit; beide schreiben denselben Wert.
    auswahlpunkt = alt.selection_point(
        name="punkt", fields=["Krankheitskosten"], nearest=True, on="click", empty=False
    )
    # Unsichtbare, aber anklickbare Senkrechten über die ganze Höhe. mark_point mit
    # opacity=0 reagiert nicht auf Klicks, eine Regel mit breitem Strich schon.
    treffer = (
        alt.Chart(kurven[["Krankheitskosten"]].drop_duplicates())
        .mark_rule(size=8)
        .encode(x="Krankheitskosten:Q", opacity=alt.value(0))
        .add_params(auswahlpunkt)
    )
    ereignis = st.altair_chart(
        diagramm + treffer, use_container_width=True, on_select="rerun"
    )

    gewaehlt = (ereignis.selection or {}).get("punkt") if ereignis else None
    if gewaehlt:
        neuer_wert = int(round(gewaehlt[0]["Krankheitskosten"] / 50) * 50)
        neuer_wert = max(0, min(maximale_krankenkosten, neuer_wert))
        if neuer_wert != erwartete_kosten:
            # Nicht direkt den Reglerschlüssel setzen - der ist in diesem Lauf schon
            # instanziert. Stattdessen vormerken und beim nächsten Lauf anwenden.
            st.session_state["_klick_kosten"] = neuer_wert
            st.rerun()

    graue_linie = (
        f"Die **rote Linie** steht bei deinen erwarteten Krankheitskosten "
        f"({chf(erwartete_kosten)} CHF) – du kannst sie direkt im Diagramm anklicken "
        f"oder den Betrag links eintragen. Fett gezeichnet ist die dort günstigste "
        f"Franchise."
    )
    if e.kipppunkt is None:
        st.caption(
            f"{graue_linie} Die tiefste Franchise ({e.tiefste_franchise} CHF) lohnt "
            f"sich bis {chf(maximale_krankenkosten)} CHF Krankheitskosten nie."
        )
    else:
        darueber = (
            " Oberhalb des Kipppunkts ändert sich die Empfehlung nicht mehr – egal "
            "wie hoch die Kosten steigen."
            if erwartete_kosten > e.kipppunkt
            else ""
        )
        st.caption(
            f"Die **grau gestrichelte Linie** ist der Kipppunkt: Ab Krankheitskosten "
            f"von **{chf(e.kipppunkt)} CHF** lohnt sich die Franchise "
            f"{e.tiefste_franchise} CHF, darunter die Franchise "
            f"{e.segmente.iloc[0]['Franchise']} CHF. Zwischen bester und schlechtester "
            f"Franchise liegen bis zu **{chf(e.max_spannweite)} CHF pro Jahr**. "
            f"{graue_linie}{darueber}"
        )

    if e.nie_optimal:
        gewinner = sorted(set(e.optimal))
        st.caption(
            f":green[Nur die Franchisen "
            f"**{' und '.join(f'{g} CHF' for g in gewinner)}** sind hier je die "
            f"günstigste Wahl. Die blass gezeichneten Stufen "
            f"{', '.join(str(f) for f in e.nie_optimal)} CHF sind bei *keinen* "
            f"Krankheitskosten optimal.]"
        )
    else:
        st.warning(
            "**Diesmal ist es anders.** In diesen Daten ist jede Franchisenstufe "
            "irgendwo die günstigste."
        )

    # ------------------------------------------------------------------ Verlauf
    # ------------------------------------- Franchisenvergleich bei den Kosten
    st.subheader("Kosten pro Franchise")
    vergleich = (
        bei_erwartung.rename("Kosten/Jahr")
        .reset_index()
        .rename(columns={"index": "Franchise"})
        .sort_values("Kosten/Jahr")
        .reset_index(drop=True)
    )
    vergleich["Franchise"] = vergleich["Franchise"].astype(int)
    vergleich["Kosten/Jahr"] = vergleich["Kosten/Jahr"].round(0)
    vergleich = _mit_abstand(vergleich, "Kosten/Jahr", "Mehrkosten/Jahr")
    vergleich["Kosten/Mt."] = (vergleich["Kosten/Jahr"] / 12).round(2)
    vergleich = _mit_abstand(vergleich, "Kosten/Mt.", "Mehrkosten/Mt.")
    st.dataframe(
        vergleich,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Franchise": st.column_config.NumberColumn(format="%d", width="small"),
            "Kosten/Jahr": st.column_config.NumberColumn(format="%.0f", width="small"),
            "Mehrkosten/Jahr": st.column_config.NumberColumn(format="%.0f", width="small"),
            "Kosten/Mt.": st.column_config.NumberColumn(format="%.2f", width="small"),
            "Mehrkosten/Mt.": st.column_config.NumberColumn(format="%.2f", width="small"),
        },
    )

    zielgruppe_daten = daten[daten["Zielgruppe"] == zielgruppe]

    # ------------------------- Die besten Angebote für die passende Franchise
    st.subheader(
        f"Die günstigsten Angebote für Franchise {beste_franchise} CHF"
    )
    st.caption(
        f"Das ist die Franchise, die bei {chf(erwartete_kosten)} CHF Krankheitskosten "
        f"am günstigsten kommt. Sortiert nach Prämie, die sieben günstigsten."
    )
    angebote = (
        zielgruppe_daten[zielgruppe_daten["Franchise"] == beste_franchise]
        .nsmallest(7, "Prämie")[
            ["Versicherername", "Tarifbezeichnung", "Tariftyp", "Prämie"]
        ]
        .reset_index(drop=True)
    )
    if angebote.empty:
        st.info("Für diese Franchise gibt es keine Angebote.")
    else:
        angebote = angebote.rename(
            columns={"Versicherername": "Versicherer", "Tarifbezeichnung": "Tarif",
                     "Tariftyp": "Typ"}
        )
        # Das Jahr ist der Massstab für die Entscheidung; die Monatsprämie steht
        # daneben, weil Policen und Vergleichsportale in Monaten rechnen.
        angebote["Prämie/Jahr"] = (angebote["Prämie"] * 12).round(0)
        angebote = _mit_abstand(angebote, "Prämie/Jahr", "Mehrkosten/Jahr")
        angebote["Prämie/Mt."] = angebote["Prämie"].round(2)
        angebote["Typ"] = angebote["Typ"].map(TARIFTYPEN_KURZ)
        angebote = angebote[
            ["Versicherer", "Tarif", "Typ", "Prämie/Jahr", "Mehrkosten/Jahr", "Prämie/Mt."]
        ]

        st.dataframe(
            angebote,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Versicherer": st.column_config.TextColumn(width="medium"),
                "Tarif": st.column_config.TextColumn(width="small"),
                "Typ": st.column_config.TextColumn(width="small"),
                "Prämie/Jahr": st.column_config.NumberColumn(format="%.0f", width="small"),
                "Mehrkosten/Jahr": st.column_config.NumberColumn(
                    format="%.0f", width="small"
                ),
                "Prämie/Mt.": st.column_config.NumberColumn(format="%.2f", width="small"),
            },
        )
        frei = zielgruppe_daten[
            (zielgruppe_daten["Tariftyp"] == "BASE")
            & (zielgruppe_daten["Franchise"] == beste_franchise)
        ]
        # angebote führt die Kurzform in der Spalte "Typ"; zielgruppe_daten hat
        # weiterhin den Rohwert in "Tariftyp".
        if not frei.empty and angebote["Typ"].iloc[0] != TARIFTYPEN_KURZ["BASE"]:
            guenstigstes = float(angebote["Prämie/Mt."].iloc[0])
            frei_monat = float(frei["Prämie"].min())
            # Nur die Zahl bekommt den Schweizer Tausendertrenner - ein replace auf
            # dem ganzen Satz würde auch die Kommas im Text ersetzen.
            aufpreis_jahr = chf((frei_monat - guenstigstes) * 12)
            st.caption(
                f"Das günstigste Angebot ist ein Modell mit **eingeschränkter "
                f"Arztwahl**. Das günstigste Standardmodell mit freier Arztwahl kostet "
                f"**{aufpreis_jahr} CHF pro Jahr mehr** ({frei_monat:.2f} statt "
                f"{guenstigstes:.2f} CHF im Monat). Ob die Einschränkung das wert ist, "
                f"bewertet dieses Werkzeug nicht."
            )

    st.download_button(
        "Kostenmatrix als CSV",
        e.kosten.to_csv().encode("utf-8"),
        file_name=f"kostenmatrix_{zielgruppe.lower()}_{kanton}.csv",
        mime="text/csv",
    )


def haushalt_ansicht(roh, kanton, region, unfalldeckung):
    st.markdown(
        "Vergleicht die **Jahresprämie des ganzen Haushalts** pro Versicherer. "
        "Ein Anbieter mit günstigen Erwachsenenprämien, aber ohne Geschwisterrabatt, "
        "kann für eine Familie teurer sein als einer mit Rabatt."
    )

    kopf = st.columns(4)
    anzahl_erw = kopf[0].number_input("Erwachsene (ab 26)", 0, 6, 2)
    anzahl_jug = kopf[1].number_input("Jugendliche (19–25)", 0, 6, 0)
    anzahl_kin = kopf[2].number_input("Kinder (0–18)", 0, 8, 2)
    franchise_erw = kopf[3].selectbox(
        "Franchise Erwachsene / Jugendliche", FRANCHISEN_ERWACHSENE, index=5
    )

    untergruppen: list[str] = []
    if anzahl_kin:
        franchise_kin = st.selectbox(
            "Franchise Kinder", FRANCHISEN_KINDER, index=len(FRANCHISEN_KINDER) - 1
        )
        st.markdown(
            "**Tarifstufe je Kind** – welche Stufe ein Kind bekommt, hängt vom "
            "Versicherer und der Familiensituation ab und steht in der Police. "
            "`K1` ist der Normaltarif, `K3`/`K5` sind Rabattstufen für weitere Kinder."
        )
        for zeile in range(0, anzahl_kin, 4):
            for spalte, i in zip(st.columns(4), range(zeile, min(zeile + 4, anzahl_kin))):
                untergruppen.append(
                    spalte.selectbox(
                        f"Kind {i + 1}", ["K1", "K3", "K4", "K5"], key=f"kind_{i}"
                    )
                )
    else:
        franchise_kin = FRANCHISEN_KINDER[-1]

    haushalt = Haushalt(
        erwachsene=int(anzahl_erw),
        jugendliche=int(anzahl_jug),
        kinder=tuple(untergruppen),
    )
    if not (haushalt.erwachsene or haushalt.jugendliche or haushalt.kinder):
        st.info("Bitte mindestens eine Person angeben.")
        return

    angebote = haushalt_angebote(
        roh,
        haushalt,
        franchise_erwachsene=franchise_erw,
        franchise_jugendliche=franchise_erw,
        franchise_kinder=franchise_kin,
        kanton=kanton,
        region=region,
        unfalldeckung=unfalldeckung,
    )
    if angebote.empty:
        st.warning(
            "Kein Versicherer führt alle verlangten Kategorien. Das passiert vor allem "
            "bei seltenen Tarifstufen – nur 1 Versicherer führt K4, 4 führen K5."
        )
        return

    guenstigstes = angebote.iloc[0]
    teuerstes = angebote.iloc[-1]
    metriken = st.columns(3)
    metriken[0].metric(
        "Günstigste Jahresprämie", f"{chf(guenstigstes['Jahresprämie'])} CHF"
    )
    metriken[1].metric(
        "Teuerste Jahresprämie", f"{chf(teuerstes['Jahresprämie'])} CHF"
    )
    metriken[2].metric(
        "Unterschied",
        f"{chf(teuerstes['Jahresprämie'] - guenstigstes['Jahresprämie'])} CHF",
        help="Pro Jahr, bei identischer Franchise und Haushaltszusammensetzung.",
    )
    st.caption(
        f"Günstigstes Angebot: **{guenstigstes['Versicherername']}** – "
        f"{guenstigstes['Tarifbezeichnung']}. {len(angebote)} Angebote führen alle "
        f"verlangten Kategorien."
    )

    # Erst Anbieter, dann die Prämie je Personenkategorie, zuletzt die Summen.
    kategorien = [
        s
        for s in angebote.columns
        if s not in {"Versicherer", "Versicherername", "Tarifbezeichnung",
                     "Monatsprämie", "Jahresprämie"}
    ]
    st.dataframe(
        angebote[
            ["Versicherername", "Tarifbezeichnung", *kategorien,
             "Monatsprämie", "Jahresprämie"]
        ].round(2),
        hide_index=True,
        use_container_width=True,
    )

    if haushalt.anzahl_kinder >= 2:
        st.subheader("Familien-Höchstgrenze der Kinder")
        kosten_je_kind = st.slider(
            "Angenommene Krankheitskosten pro Kind und Jahr (CHF)",
            0, 10000, 3000, step=250,
        )
        betrag, gedeckelt = kinder_kostenbeteiligung(
            [float(kosten_je_kind)] * haushalt.anzahl_kinder, franchise_kin
        )
        ohne_deckel = sum(
            min(kosten_je_kind, franchise_kin)
            + min(max(0, kosten_je_kind - franchise_kin) * 0.1, 350)
            for _ in range(haushalt.anzahl_kinder)
        )
        links, rechts = st.columns(2)
        links.metric("Kostenbeteiligung aller Kinder", f"{chf(betrag)} CHF")
        rechts.metric(
            "Ohne Deckelung wären es",
            f"{chf(ohne_deckel)} CHF",
            delta=f"−{chf(ohne_deckel - betrag)} CHF" if gedeckelt else "nicht erreicht",
            delta_color="normal" if gedeckelt else "off",
        )
        st.caption(
            f"Art. 93 Abs. 3 KVV: Sind mehrere Kinder einer Familie beim gleichen "
            f"Versicherer versichert, ist ihre Kostenbeteiligung auf das Zweifache des "
            f"Höchstbetrages je Kind begrenzt – hier 2 × ({franchise_kin} + 350) = "
            f"{chf(2 * (franchise_kin + 350))} CHF. Bei unterschiedlichen Franchisen der "
            f"Kinder setzt der Versicherer die Höchstbeteiligung fest; hier wird eine "
            f"gemeinsame Franchise angenommen."
        )


# Ein Klick ins Diagramm merkt den Wert vor; angewendet wird er hier, bevor der
# Regler entsteht.
if "_klick_kosten" in st.session_state:
    st.session_state["erwartete_kosten"] = st.session_state.pop("_klick_kosten")

with st.sidebar:
    st.header("Deine Angaben")

    if st.button("Prämiendaten neu laden"):
        st.cache_data.clear()
        praemien(0)
        st.rerun()

    roh = praemien(7)

    wohnort = wohnort_waehlen()

    alter = st.number_input(
        "Alter",
        min_value=0,
        max_value=120,
        value=40,
        step=1,
        help="Daraus ergibt sich die Altersklasse: Kinder bis 18, junge Erwachsene "
        "19 bis 25, danach Erwachsene.",
    )
    zielgruppe = zielgruppe_fuer_alter(int(alter))
    st.caption(f"Altersklasse: **{zielgruppe}**")

    # Die Unfalldeckung wird immer gefragt, nie aus dem Alter abgeleitet: Ob jemand
    # über einen Arbeitgeber versichert ist, weiss nur er selbst. Vorgewählt ist der
    # Normalfall - bei Erwachsenen "ohne" (meist über den Arbeitgeber gedeckt), bei
    # Kindern und jungen Erwachsenen "mit".
    unfall = st.radio(
        "Unfalldeckung",
        ["MIT-UNF", "OHN-UNF"],
        index=1 if zielgruppe == "Erwachsene" else 0,
        format_func=lambda u: (
            "mit – nicht über einen Arbeitgeber versichert"
            if u == "MIT-UNF"
            else "ohne – über einen Arbeitgeber versichert"
        ),
        help="Wer mindestens acht Stunden pro Woche bei demselben Arbeitgeber "
        "arbeitet, ist dort gegen Unfall versichert und braucht die Deckung in der "
        "Grundversicherung nicht. Sonst muss sie eingeschlossen sein.",
    )
    unfalldeckung = {zielgruppe: unfall}

    st.session_state.setdefault("erwartete_kosten", 1000)
    erwartete_kosten = st.number_input(
        "Erwartete Krankheitskosten pro Jahr (CHF)",
        min_value=0,
        step=100,
        key="erwartete_kosten",
        help="Der wichtigste Wert neben dem Alter. Arztbesuche, Medikamente, "
        "Therapien – alles, was über die Grundversicherung abgerechnet wird. "
        "Nach oben offen; oberhalb des Kipppunkts ändert sich die Empfehlung "
        "allerdings nicht mehr.",
    )

    # Die Rückerstattung der Umweltabgaben ist für alle gleich hoch und ändert
    # jährlich. Danach zu fragen hiesse, eine Zahl zu verlangen, die niemand im
    # Kopf hat - sie wird deshalb nur noch genannt.
    umweltabgabe = umweltabgabe_standard
    st.caption(
        f"Rückerstattung Umweltabgaben: **{umweltabgabe * 12:.2f} CHF pro Jahr** "
        f"({umweltabgabe:.2f} pro Monat). Wird von der Prämie abgezogen und ist für "
        f"alle Versicherten gleich."
    )

    # Der Tariftyp entscheidet über die freie Arztwahl und kostet schnell mehr als
    # die ganze Franchisenfrage - er gehört nicht in eine eingeklappte Schublade.
    tariftypen = st.multiselect(
        "Tarifmodelle",
        list(TARIFTYPEN),
        default=list(TARIFTYPEN),
        format_func=lambda t: TARIFTYPEN[t],
        help="Das Standardmodell lässt die Arztwahl frei; die übrigen schränken sie "
        "ein und sind dafür günstiger. Abwählen, was für dich nicht in Frage kommt.",
    )
    if not tariftypen:
        st.caption("Ohne Tarifmodell gibt es nichts zu vergleichen.")

    if zielgruppe == "Kinder":
        kinder_untergruppen = st.multiselect(
            "Tarifstufe des Kindes",
            list(KINDER_UNTERGRUPPEN),
            default=["K1"],
            format_func=lambda k: f"{k} – {KINDER_UNTERGRUPPEN[k]}",
            help="Geschwisterrabatte, benannt wie in der Tarifliste des BAG. "
            "Welche Stufe für dein Kind gilt, hängt von der Zahl der Kinder "
            "derselben Familie beim gleichen Versicherer ab und steht in der "
            "Police. Mehrere Kinder vergleichst du besser im Register «Haushalt».",
        )
    else:
        kinder_untergruppen = ["K1"]

st.title("Welche Franchise lohnt sich?")
st.caption(
    "Die Grundversicherung bietet mehrere Franchisen zur Auswahl. Diese App rechnet für "
    "deine Angaben nach, welche davon überhaupt je die günstigste ist und ab welchen "
    "jährlichen Krankheitskosten es von der einen zur anderen kippt. "
    "Datenquelle: BAG-Prämiendaten über opendata.swiss."
)

tab_person, tab_haushalt = st.tabs(["Einzelperson", "Haushalt"])

with tab_person:
    if wohnort is None:
        st.info("Bitte links eine gültige Postleitzahl eingeben.")
    else:
        einzelperson_ansicht(
            roh, wohnort[0], wohnort[1], wohnort[2], zielgruppe, unfalldeckung,
            tariftypen, kinder_untergruppen, umweltabgabe, erwartete_kosten,
        )

with tab_haushalt:
    if wohnort is None:
        st.info("Bitte links eine gültige Postleitzahl eingeben.")
    else:
        haushalt_ansicht(
            roh, wohnort[0], wohnort[1],
            {"Erwachsene": "OHN-UNF", "Jugendliche": "OHN-UNF", "Kinder": "MIT-UNF"},
        )
