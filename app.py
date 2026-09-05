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
from utils import beste_praemien, berechne_kipppunkt, get_data, lade_praemien

st.set_page_config(page_title="Krankenkassen-Kipppunkt", page_icon="🏥", layout="wide")


@st.cache_data(show_spinner="Lade BAG-Prämiendaten…")
def praemien(max_alter_tage: int):
    return lade_praemien(max_alter_tage)


with st.sidebar:
    st.header("Einstellungen")

    if st.button("Prämiendaten neu laden"):
        st.cache_data.clear()
        praemien(0)
        st.rerun()

    roh = praemien(7)
    kantone = sorted(roh["Kanton"].dropna().unique())
    kanton = st.selectbox(
        "Kanton", kantone, index=kantone.index(kanton_standard) if kanton_standard in kantone else 0
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
        help="Wird von der Monatsprämie abgezogen. Ändert jedes Jahr.",
    )

    zielgruppen = st.multiselect(
        "Zielgruppen",
        list(ALTERSKLASSEN.values()),
        default=["Erwachsene", "Kinder"],
    )

    max_kosten = st.slider(
        "Maximale Krankheitskosten (CHF)",
        min_value=2000,
        max_value=20000,
        value=maximale_krankenkosten,
        step=1000,
    )

    erwartete_kosten = st.slider(
        "Erwartete Krankheitskosten pro Jahr (CHF)",
        min_value=0,
        max_value=max_kosten,
        value=min(1000, max_kosten),
        step=50,
        help="Für den direkten Franchisenvergleich weiter unten.",
    )

    toleranz = st.slider(
        "Spürbarkeitsschwelle (CHF pro Jahr)",
        min_value=10,
        max_value=200,
        value=50,
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
            for zg in zielgruppen
        }
        tariftypen = st.multiselect(
            "Tariftypen",
            list(TARIFTYPEN),
            default=list(TARIFTYPEN),
            format_func=lambda t: TARIFTYPEN[t],
        )
        kinder_untergruppen = st.multiselect(
            "Altersuntergruppen Kinder",
            ["K1", "K3", "K4", "K5"],
            default=list(KINDER_UNTERGRUPPEN_STANDARD),
            help="Nicht offiziell dokumentiert. K1 ist der Normalfall, "
            "K3/K5 enthalten Familienrabatte für weitere Kinder.",
        )

st.title("Krankenkassen-Kipppunkt")
st.caption(
    "Ab welchen jährlichen Krankheitskosten lohnt sich die tiefste Franchise? "
    "Datenquelle: BAG-Prämienvergleich (priminfo.admin.ch)."
)

if not zielgruppen:
    st.info("Bitte mindestens eine Zielgruppe auswählen.")
    st.stop()

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
    st.stop()

ergebnisse = berechne_kipppunkt(beste, umweltabgabe, max_kosten)

spalten = st.columns(len(ergebnisse))
for spalte, e in zip(spalten, ergebnisse):
    with spalte:
        if e.kipppunkt is None:
            st.metric(f"{e.zielgruppe}: Kipppunkt", "—")
            st.caption(
                f"Franchise {e.tiefste_franchise} CHF lohnt sich bis "
                f"{max_kosten} CHF Krankheitskosten nie."
            )
        else:
            st.metric(
                f"{e.zielgruppe}: tiefste Franchise ({e.tiefste_franchise} CHF) ab",
                f"{e.kipppunkt:,} CHF".replace(",", "'"),
            )
            beste_alternative = e.segmente.iloc[0]["Franchise"]
            spuerbar = e.materieller_kipppunkt(toleranz)
            wann = (
                f"Um mehr als {toleranz:.0f} CHF pro Jahr erst ab {spuerbar} CHF."
                if spuerbar is not None
                else f"Mehr als {toleranz:.0f} CHF pro Jahr bringt sie nie."
            )
            st.caption(
                f"Darunter ist Franchise {beste_alternative} CHF günstiger. {wann} "
                f"Grösster Vorteil überhaupt: **{e.max_vorteil:.0f} CHF pro Jahr**."
            )

groesster = max((e.max_vorteil for e in ergebnisse), default=0.0)
spannweiten = {}
for e in ergebnisse:
    angebote = daten[
        (daten["Zielgruppe"] == e.zielgruppe)
        & (daten["Franchise"] == e.tiefste_franchise)
    ]["Prämie"]
    if not angebote.empty:
        spannweiten[e.zielgruppe] = (angebote.max() - angebote.min()) * 12

if spannweiten:
    grösste_spannweite = f"{max(spannweiten.values()):,.0f}".replace(",", "'")
    st.info(
        f"**Die Franchisenwahl ist die kleinere Frage.** Über den ganzen Bereich bis "
        f"{max_kosten} CHF bringt die tiefste Franchise höchstens "
        f"**{groesster:.0f} CHF pro Jahr** gegenüber der nächstbesten Stufe – die "
        f"Prämienrabatte pro Stufe sind so geregelt, dass sich die Varianten fast die "
        f"Waage halten. Zwischen günstigstem und teuerstem Versicherer liegen bei "
        f"gleicher Franchise dagegen bis zu **{grösste_spannweite} CHF pro Jahr**. "
        f"Dort liegt das Geld."
    )

for e in ergebnisse:
    st.subheader(e.zielgruppe)

    kurven = (
        e.kosten.reset_index()
        .melt(id_vars="Krankheitskosten", var_name="Franchise", value_name="Jahreskosten")
    )
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
            tooltip=["Krankheitskosten", "Franchise", alt.Tooltip("Jahreskosten", format=".2f")],
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

    bei_erwartung = e.kosten.loc[erwartete_kosten]
    vergleich = (
        bei_erwartung.rename("Jahreskosten")
        .reset_index()
        .rename(columns={"index": "Franchise"})
        .sort_values("Jahreskosten")
        .reset_index(drop=True)
    )
    vergleich["Franchise"] = vergleich["Franchise"].astype(int)
    vergleich["Mehrkosten"] = (vergleich["Jahreskosten"] - vergleich["Jahreskosten"].min()).round(2)
    vergleich["Jahreskosten"] = vergleich["Jahreskosten"].round(2)
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
        tabelle["Prämie abzgl. Umweltabgabe"] = (tabelle["Prämie"] - umweltabgabe).round(2)
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
