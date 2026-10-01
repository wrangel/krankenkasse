import altair as alt
import pandas as pd
import streamlit as st

from constants import (
    ALTERSKLASSEN,
    KINDER_UNTERGRUPPEN_STANDARD,
    REGIONEN,
    TARIFTYPEN,
    kanton_standard,
    maximale_krankenkosten,
    region_standard,
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


def einzelperson_ansicht(
    roh, kanton, region, zielgruppen, unfalldeckung, tariftypen, kinder_untergruppen,
    umweltabgabe, max_kosten, erwartete_kosten, toleranz,
):
    if not zielgruppen:
        st.info("Bitte mindestens eine Zielgruppe auswählen.")
        return

    daten = get_data(
        roh,
        kanton=kanton,
        region=region,
        zielgruppen=tuple(zielgruppen),
        unfalldeckung=unfalldeckung,
        kinder_untergruppen=tuple(kinder_untergruppen),
        tariftypen=tuple(tariftypen) if tariftypen else None,
    )
    beste = beste_praemien(daten)
    if beste.empty:
        st.warning("Für diese Auswahl gibt es keine Prämien.")
        return

    ergebnisse = berechne_kipppunkt(beste, umweltabgabe, max_kosten)
    praemienjahr = int(roh["Geschäftsjahr"].max())

    for spalte, e in zip(st.columns(len(ergebnisse)), ergebnisse):
        with spalte:
            if e.kipppunkt is None:
                st.metric(f"{e.zielgruppe}: Kipppunkt", "—")
                st.caption(
                    f"Franchise {e.tiefste_franchise} CHF lohnt sich bis "
                    f"{max_kosten} CHF Krankheitskosten nie."
                )
                continue
            st.metric(
                f"{e.zielgruppe}: tiefste Franchise ({e.tiefste_franchise} CHF) ab",
                f"{chf(e.kipppunkt)} CHF",
            )
            spuerbar = e.materieller_kipppunkt(toleranz)
            wann = (
                f"Um mehr als {toleranz:.0f} CHF pro Jahr erst ab {spuerbar} CHF."
                if spuerbar is not None
                else f"Mehr als {toleranz:.0f} CHF pro Jahr bringt sie nie."
            )
            st.caption(
                f"Darunter ist Franchise {e.segmente.iloc[0]['Franchise']} CHF günstiger. "
                f"{wann} Gegenüber der nächstbesten Stufe höchstens "
                f"{e.max_vorteil:.0f} CHF pro Jahr – zwischen bester und schlechtester "
                f"Franchise dagegen bis zu **{chf(e.max_spannweite)} CHF**."
            )

    groesster = max((e.max_vorteil for e in ergebnisse), default=0.0)
    spannweiten = [
        (gruppe["Prämie"].max() - gruppe["Prämie"].min()) * 12
        for e in ergebnisse
        for gruppe in [
            daten[
                (daten["Zielgruppe"] == e.zielgruppe)
                & (daten["Franchise"] == e.tiefste_franchise)
            ]
        ]
        if not gruppe.empty
    ]
    groesste_spannweite = max((e.max_spannweite for e in ergebnisse), default=0.0)

    for e in ergebnisse:
        if not e.nie_optimal:
            st.warning(
                f"**{e.zielgruppe}: Diesmal ist es anders.** In diesen Daten ist jede "
                f"Franchisenstufe irgendwo die günstigste – die sonst übliche Regel "
                f"«nur die höchste oder die tiefste zählt» trifft hier nicht zu."
            )
            continue
        gewinner = sorted(set(e.optimal))
        st.success(
            f"**{e.zielgruppe}: Es sind nicht {len(e.kosten.columns)} Möglichkeiten, "
            f"sondern {len(gewinner)}.** Nur die Franchisen "
            f"**{' und '.join(f'{g} CHF' for g in gewinner)}** sind hier je die "
            f"günstigste Wahl. Die Stufen "
            f"{', '.join(f'{f}' for f in e.nie_optimal)} CHF sind bei *keinen* "
            f"Krankheitskosten optimal – es gibt immer eine der beiden anderen, die "
            f"günstiger kommt."
        )

    st.caption(
        f"Diese Aussage ist **kein Gesetz, sondern ein Befund aus den Daten** des "
        f"Prämienjahres {praemienjahr}. Die Verordnung schreibt die Rabatte nicht vor: "
        f"Sie deckelt sie nur (höchstens 70 % des übernommenen Risikos, Art. 95 "
        f"Abs. 2bis KVV) – die Höhe legen die Versicherer selbst fest (Art. 95 "
        f"Abs. 1bis KVV). Die Prämien werden jedes Jahr neu festgesetzt, deshalb rechnet "
        f"diese App den Befund bei jedem Aufruf neu aus, statt ihn anzunehmen."
    )

    if spannweiten:
        st.info(
            f"**Die Wahl zwischen den beiden lohnt sich – aber nicht auf den Franken "
            f"genau.** Wer seine Krankheitskosten realistisch einschätzt, spart bis zu "
            f"**{chf(groesste_spannweite)} CHF pro Jahr** gegenüber der schlechteren der "
            f"beiden. Rund um den Kipppunkt selbst geht es dagegen um Rappen – dort ist "
            f"die Entscheidung fast beliebig. Zum Vergleich: zwischen günstigstem und "
            f"teuerstem Versicherer liegen bei gleicher Franchise bis zu "
            f"**{chf(max(spannweiten))} CHF pro Jahr**."
        )

    for e in ergebnisse:
        st.subheader(e.zielgruppe)

        kurven = e.kosten.reset_index().melt(
            id_vars="Krankheitskosten", var_name="Franchise", value_name="Jahreskosten"
        )
        dominiert = set(e.nie_optimal)
        kurven["Rolle"] = [
            "nie optimal" if f in dominiert else "entscheidend" for f in kurven["Franchise"]
        ]
        kurven["Franchise"] = kurven["Franchise"].astype(str)

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
                opacity=alt.Opacity(
                    "Rolle:N",
                    scale=alt.Scale(
                        domain=["entscheidend", "nie optimal"], range=[1.0, 0.25]
                    ),
                    legend=alt.Legend(title="Rolle"),
                ),
                strokeWidth=alt.StrokeWidth(
                    "Rolle:N",
                    scale=alt.Scale(
                        domain=["entscheidend", "nie optimal"], range=[3, 1]
                    ),
                    legend=None,
                ),
                tooltip=[
                    "Krankheitskosten",
                    "Franchise",
                    alt.Tooltip("Jahreskosten", format=".2f"),
                    "Rolle",
                ],
            )
            .properties(height=340)
        )
        if e.kipppunkt is not None:
            diagramm += (
                alt.Chart(pd.DataFrame({"k": [e.kipppunkt]}))
                .mark_rule(strokeDash=[6, 4], color="crimson")
                .encode(x="k:Q")
            )
        diagramm += (
            alt.Chart(pd.DataFrame({"k": [erwartete_kosten]}))
            .mark_rule(color="grey")
            .encode(x="k:Q")
        )
        st.altair_chart(diagramm, use_container_width=True)

        vergleich = (
            e.kosten.loc[erwartete_kosten]
            .rename("Jahreskosten")
            .reset_index()
            .rename(columns={"index": "Franchise"})
            .sort_values("Jahreskosten")
            .reset_index(drop=True)
        )
        vergleich["Franchise"] = vergleich["Franchise"].astype(int)
        vergleich["Mehrkosten"] = (
            vergleich["Jahreskosten"] - vergleich["Jahreskosten"].min()
        ).round(2)
        vergleich["Jahreskosten"] = vergleich["Jahreskosten"].round(2)
        relevante = " oder ".join(f"{g}" for g in sorted(set(e.optimal)))
        vergleich["Je optimal?"] = [
            f"nie – immer schlechter als {relevante}" if f in dominiert else "ja"
            for f in vergleich["Franchise"]
        ]
        empfehlung = vergleich.iloc[0]
        st.markdown(
            f"Bei **{erwartete_kosten} CHF** Krankheitskosten ist für {e.zielgruppe} "
            f"die Franchise **{int(empfehlung['Franchise'])} CHF** am günstigsten "
            f"({empfehlung['Jahreskosten']:.2f} CHF pro Jahr)."
        )
        st.dataframe(vergleich, hide_index=True, use_container_width=True)

        links, rechts = st.columns([3, 2])
        with links:
            st.markdown("**Günstigstes Angebot pro Franchise**")
            tabelle = beste[beste["Zielgruppe"] == e.zielgruppe][
                ["Franchise", "Prämie", "Versicherername", "Tarifbezeichnung", "Tariftyp"]
            ].copy()
            tabelle["Prämie abzgl. Umweltabgabe"] = (
                tabelle["Prämie"] - umweltabgabe
            ).round(2)
            tabelle["Tariftyp"] = tabelle["Tariftyp"].map(TARIFTYPEN)
            st.dataframe(tabelle, hide_index=True, use_container_width=True)
        with rechts:
            st.markdown("**Optimale Franchise nach Krankheitskosten**")
            st.dataframe(e.segmente, hide_index=True, use_container_width=True)

        st.download_button(
            f"Kostenmatrix {e.zielgruppe} als CSV",
            e.kosten.to_csv().encode("utf-8"),
            file_name=f"kostenmatrix_{e.zielgruppe.lower()}_{kanton}.csv",
            mime="text/csv",
            key=f"dl_{e.zielgruppe}",
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


with st.sidebar:
    st.header("Einstellungen")

    if st.button("Prämiendaten neu laden"):
        st.cache_data.clear()
        praemien(0)
        st.rerun()

    roh = praemien(7)
    kantone = sorted(roh["Kanton"].dropna().unique())
    kanton = st.selectbox(
        "Kanton",
        kantone,
        index=kantone.index(kanton_standard) if kanton_standard in kantone else 0,
    )
    verfuegbar = sorted(roh.loc[roh["Kanton"] == kanton, "Region"].dropna().unique())
    region = st.selectbox(
        "Prämienregion",
        verfuegbar,
        index=verfuegbar.index(region_standard) if region_standard in verfuegbar else 0,
        format_func=lambda r: f"{REGIONEN.get(r, r)} ({r.split()[-1]})",
    )

    umweltabgabe = st.number_input(
        "Umweltabgabe pro Monat (CHF)",
        min_value=0.0,
        max_value=50.0,
        value=umweltabgabe_standard,
        step=0.05,
        help="Wird von der Monatsprämie abgezogen. Verschiebt den Kipppunkt nicht, "
        "da sie jede Franchise gleich entlastet.",
    )

    zielgruppen = st.multiselect(
        "Zielgruppen", list(ALTERSKLASSEN.values()), default=["Erwachsene", "Kinder"]
    )

    max_kosten = st.slider(
        "Maximale Krankheitskosten (CHF)", 2000, 20000, maximale_krankenkosten, step=1000
    )
    erwartete_kosten = st.slider(
        "Erwartete Krankheitskosten pro Jahr (CHF)",
        0,
        max_kosten,
        min(1000, max_kosten),
        step=50,
        help="Für den direkten Franchisenvergleich.",
    )
    toleranz = st.slider(
        "Spürbarkeitsschwelle (CHF pro Jahr)",
        10,
        200,
        50,
        step=10,
        help="Ab welchem jährlichen Unterschied ein Franchisenwechsel für dich "
        "überhaupt der Rede wert ist.",
    )

    with st.expander("Feineinstellungen"):
        unfalldeckung = {
            zg: st.radio(
                f"Unfalldeckung {zg}",
                ["OHN-UNF", "MIT-UNF"],
                index=1 if zg == "Kinder" else 0,
                format_func=lambda u: "mit Unfall" if u == "MIT-UNF" else "ohne Unfall",
                horizontal=True,
                key=f"unf_{zg}",
            )
            for zg in ALTERSKLASSEN.values()
        }
        tariftypen = st.multiselect(
            "Tariftypen",
            list(TARIFTYPEN),
            default=list(TARIFTYPEN),
            format_func=lambda t: TARIFTYPEN[t],
        )
        kinder_untergruppen = st.multiselect(
            "Altersuntergruppen Kinder (Einzelperson)",
            ["K1", "K3", "K4", "K5"],
            default=list(KINDER_UNTERGRUPPEN_STANDARD),
            help="Nicht offiziell dokumentiert. K1 ist der Normaltarif, K3/K5 sind "
            "Rabattstufen für weitere Kinder. Nur K1 führen alle Versicherer.",
        )

st.title("Welche Franchise lohnt sich?")
st.caption(
    "Die Grundversicherung bietet mehrere Franchisen zur Auswahl. Diese App rechnet für "
    "deine Auswahl nach, welche davon überhaupt je die günstigste sind und ab welchen "
    "jährlichen Krankheitskosten es von der einen zur anderen kippt. "
    "Datenquelle: BAG-Prämiendaten über opendata.swiss."
)

tab_person, tab_haushalt = st.tabs(["Einzelperson", "Haushalt"])

with tab_person:
    einzelperson_ansicht(
        roh, kanton, region, zielgruppen, unfalldeckung, tariftypen,
        kinder_untergruppen, umweltabgabe, max_kosten, erwartete_kosten, toleranz,
    )

with tab_haushalt:
    haushalt_ansicht(roh, kanton, region, unfalldeckung)
