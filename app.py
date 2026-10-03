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
    beste_praemien,
    berechne_kipppunkt,
    erlaubte_kinderstufen,
    get_data,
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


def person_ansicht(
    roh, kanton, region, zielgruppe, unfalldeckung, tariftypen,
    kinder_untergruppen, umweltabgabe, erwartete_kosten, schluessel,
):
    """Zeigt eine Person und gibt ihre Eckwerte für die Haushaltssumme zurück."""
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
        return None

    # Gerechnet wird immer über einen Bereich, der die eingegebenen Kosten
    # einschliesst - sonst fiele ein hoher Wert aus der Kostenmatrix.
    rechenbereich = max(maximale_krankenkosten, int(erwartete_kosten) + 2000)
    ergebnisse = berechne_kipppunkt(beste, umweltabgabe, rechenbereich)
    if not ergebnisse:
        st.warning("Für diese Auswahl lässt sich nichts berechnen.")
        return None
    e = ergebnisse[0]

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
        diagramm + treffer, use_container_width=True, on_select="rerun",
        key=f"diagramm_{schluessel}",
    )

    gewaehlt = (ereignis.selection or {}).get("punkt") if ereignis else None
    if gewaehlt:
        neuer_wert = int(round(gewaehlt[0]["Krankheitskosten"] / 50) * 50)
        neuer_wert = max(0, min(maximale_krankenkosten, neuer_wert))
        if neuer_wert != erwartete_kosten:
            # Nicht direkt den Reglerschlüssel setzen - der ist in diesem Lauf schon
            # instanziert. Stattdessen vormerken und beim nächsten Lauf anwenden.
            st.session_state["_klick_kosten"] = (schluessel, neuer_wert)
            st.rerun()

    # Eine Bildunterschrift statt zweier: Beide erklärten dasselbe Bild - die
    # senkrechten Linien und die blassen Kurven -, und zwei Absätze hintereinander
    # lesen sich wie zwei Themen.
    teile = [
        f"Die **rote Linie** steht bei deinen erwarteten Krankheitskosten "
        f"({chf(erwartete_kosten)} CHF); du kannst sie im Diagramm anklicken oder den "
        f"Betrag links eintragen. Fett gezeichnet ist die dort günstigste Franchise."
    ]
    if e.kipppunkt is None:
        teile.append(
            f"Die tiefste Franchise ({e.tiefste_franchise} CHF) lohnt sich im "
            f"gezeigten Bereich nie."
        )
    else:
        teile.append(
            f"Die **grau gestrichelte Linie** ist der Kipppunkt: Ab "
            f"**{chf(e.kipppunkt)} CHF** lohnt sich die Franchise "
            f"{e.tiefste_franchise} CHF, darunter die Franchise "
            f"{e.segmente.iloc[0]['Franchise']} CHF. Zwischen bester und schlechtester "
            f"Franchise liegen bis zu **{chf(e.max_spannweite)} CHF pro Jahr**."
        )
        if erwartete_kosten > e.kipppunkt:
            teile.append(
                "Oberhalb des Kipppunkts ändert sich die Empfehlung nicht mehr – "
                "egal wie hoch die Kosten steigen."
            )
    if e.nie_optimal:
        gewinner = sorted(set(e.optimal))
        teile.append(
            f"Nur die Franchisen "
            f"**{' und '.join(f'{g} CHF' for g in gewinner)}** sind hier je die "
            f"günstigste Wahl; die blass gezeichneten Stufen "
            f"{', '.join(str(f) for f in e.nie_optimal)} CHF sind bei *keinen* "
            f"Krankheitskosten optimal."
        )
    else:
        teile.append(
            "In diesen Daten ist jede Franchisenstufe irgendwo die günstigste – "
            "sonst gewinnen nur die höchste und die tiefste."
        )
    st.caption(" ".join(teile))

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
    vergleich["Kosten/Monat"] = (vergleich["Kosten/Jahr"] / 12).round(2)
    vergleich = _mit_abstand(vergleich, "Kosten/Monat", "Mehrkosten/Monat")
    st.dataframe(
        vergleich,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Franchise": st.column_config.NumberColumn(format="%d", width="small"),
            "Kosten/Jahr": st.column_config.NumberColumn(format="%.0f", width="small"),
            "Mehrkosten/Jahr": st.column_config.NumberColumn(format="%.0f", width="small"),
            "Kosten/Monat": st.column_config.NumberColumn(format="%.2f", width="small"),
            "Mehrkosten/Monat": st.column_config.NumberColumn(format="%.2f", width="small"),
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
        angebote["Prämie/Monat"] = angebote["Prämie"].round(2)
        angebote["Typ"] = angebote["Typ"].map(TARIFTYPEN_KURZ)
        angebote = angebote[
            ["Versicherer", "Tarif", "Typ", "Prämie/Jahr", "Mehrkosten/Jahr", "Prämie/Monat"]
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
                "Prämie/Monat": st.column_config.NumberColumn(format="%.2f", width="small"),
            },
        )
        frei = zielgruppe_daten[
            (zielgruppe_daten["Tariftyp"] == "BASE")
            & (zielgruppe_daten["Franchise"] == beste_franchise)
        ]
        # angebote führt die Kurzform in der Spalte "Typ"; zielgruppe_daten hat
        # weiterhin den Rohwert in "Tariftyp".
        if not frei.empty and angebote["Typ"].iloc[0] != TARIFTYPEN_KURZ["BASE"]:
            guenstigstes = float(angebote["Prämie/Monat"].iloc[0])
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
        key=f"csv_{schluessel}",
    )

    guenstigstes = angebote.iloc[0] if not angebote.empty else None
    return {
        "zielgruppe": zielgruppe,
        "franchise": beste_franchise,
        "jahreskosten": float(bei_erwartung.min()),
        "versicherer": guenstigstes["Versicherer"] if guenstigstes is not None else "—",
        "tarif": guenstigstes["Tarif"] if guenstigstes is not None else "—",
        "praemie_jahr": float(guenstigstes["Prämie/Jahr"]) if guenstigstes is not None else 0.0,
    }


def person_formular(nummer: int, person: dict, anzahl_personen: int) -> dict:
    """Eingaben einer Person. Gibt den aktualisierten Eintrag zurück."""
    kopf = st.columns([2, 3, 3, 1])
    alter = kopf[0].number_input(
        "Alter",
        min_value=0,
        max_value=120,
        value=int(person["alter"]),
        step=1,
        key=f"alter_{person['id']}",
    )
    zielgruppe = zielgruppe_fuer_alter(int(alter))

    unfall = kopf[1].radio(
        "Unfalldeckung",
        ["MIT-UNF", "OHN-UNF"],
        index=1 if zielgruppe == "Erwachsene" else 0,
        format_func=lambda u: "mit" if u == "MIT-UNF" else "ohne",
        horizontal=True,
        key=f"unfall_{person['id']}",
        help="Wer mindestens acht Stunden pro Woche bei demselben Arbeitgeber "
        "arbeitet, ist dort gegen Unfall versichert.",
    )

    schluessel = f"kosten_{person['id']}"
    st.session_state.setdefault(schluessel, int(person["kosten"]))
    kosten = kopf[2].number_input(
        "Erwartete Krankheitskosten pro Jahr (CHF)",
        min_value=0,
        step=100,
        key=schluessel,
    )

    # Die erste Person lässt sich nicht entfernen - ohne sie gäbe es nichts zu zeigen.
    if anzahl_personen > 1:
        kopf[3].markdown("<div style='height:1.8rem'></div>", unsafe_allow_html=True)
        if kopf[3].button("Entfernen", key=f"weg_{person['id']}"):
            st.session_state["personen"] = [
                p for p in st.session_state["personen"] if p["id"] != person["id"]
            ]
            st.rerun()

    return {"id": person["id"], "alter": int(alter), "unfall": unfall, "kosten": int(kosten)}


def haushalt_summe(ergebnisse: list[dict], anzahl_kinder: int) -> None:
    """Die Summe über alle Personen - das, wonach am Ende gefragt ist."""
    if not ergebnisse:
        return

    gesamt = sum(e["jahreskosten"] for e in ergebnisse)
    praemien = sum(e["praemie_jahr"] for e in ergebnisse)

    st.markdown("---")
    st.header("Gesamtkosten des Haushalts")

    spalten = st.columns(3)
    spalten[0].metric("Pro Jahr", f"{chf(gesamt)} CHF")
    spalten[1].metric("Pro Monat", f"{chf(gesamt / 12, 2)} CHF")
    spalten[2].metric("Personen", str(len(ergebnisse)))
    st.caption(
        f"Summe über alle Personen: Prämien ({chf(praemien)} CHF) plus Franchise und "
        f"Selbstbehalt bei den jeweils angegebenen Krankheitskosten, je zum "
        f"günstigsten Angebot."
    )

    uebersicht = pd.DataFrame(
        [
            {
                "Person": f"{i}. {e['zielgruppe']}",
                "Franchise": e["franchise"],
                "Versicherer": e["versicherer"],
                "Tarif": e["tarif"],
                "Kosten/Jahr": round(e["jahreskosten"]),
                "Kosten/Monat": round(e["jahreskosten"] / 12, 2),
            }
            for i, e in enumerate(ergebnisse, start=1)
        ]
    )
    st.dataframe(
        uebersicht,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Franchise": st.column_config.NumberColumn(format="%d", width="small"),
            "Kosten/Jahr": st.column_config.NumberColumn(format="%.0f", width="small"),
            "Kosten/Monat": st.column_config.NumberColumn(format="%.2f", width="small"),
        },
    )

    if anzahl_kinder >= 2:
        st.caption(
            f"Die Kinderprämien enthalten den Geschwisterrabatt, soweit er bei "
            f"{anzahl_kinder} Kindern erreichbar ist. Zusätzlich begrenzt Art. 93 "
            f"Abs. 3 KVV die Kostenbeteiligung aller Kinder beim gleichen "
            f"Versicherer auf das Zweifache des Höchstbetrages je Kind – diese "
            f"Deckelung ist in den Zahlen oben **nicht** berücksichtigt, die reale "
            f"Belastung kann also tiefer ausfallen."
        )


# Ein Klick ins Diagramm merkt den Wert vor; angewendet wird er hier, bevor die
# Eingabefelder entstehen.
if "_klick_kosten" in st.session_state:
    schluessel, wert = st.session_state.pop("_klick_kosten")
    st.session_state[schluessel] = wert

st.session_state.setdefault(
    "personen", [{"id": 1, "alter": 40, "unfall": "OHN-UNF", "kosten": 1000}]
)

with st.sidebar:
    st.header("Wohnort und Modelle")

    if st.button("Prämiendaten neu laden"):
        st.cache_data.clear()
        praemien(0)
        st.rerun()

    roh = praemien(7)
    wohnort = wohnort_waehlen()

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

    umweltabgabe = umweltabgabe_standard
    st.caption(
        f"Rückerstattung Umweltabgaben: **{umweltabgabe * 12:.2f} CHF pro Jahr** "
        f"({umweltabgabe:.2f} pro Monat). Wird von der Prämie abgezogen und ist für "
        f"alle Versicherten gleich."
    )

st.title("Welche Franchise lohnt sich?")
st.caption(
    "Die Grundversicherung bietet mehrere Franchisen zur Auswahl. Diese App rechnet für "
    "jede Person nach, welche davon überhaupt je die günstigste ist und ab welchen "
    "jährlichen Krankheitskosten es von der einen zur anderen kippt. "
    "Datenquelle: BAG-Prämiendaten über opendata.swiss."
)

if wohnort is None:
    st.info("Bitte links eine gültige Postleitzahl eingeben.")
    st.stop()

st.markdown(f"**{wohnort[2]}**")

# Erst alle Formulare, dann rechnen: Die Tarifstufe eines Kindes hängt davon ab,
# wie viele Kinder insgesamt im Haushalt leben.
personen = st.session_state["personen"]
aktualisiert = []
for nummer, person in enumerate(personen, start=1):
    with st.container(border=True):
        st.markdown(f"**{nummer}. Person**")
        aktualisiert.append(person_formular(nummer, person, len(personen)))
st.session_state["personen"] = aktualisiert

if st.button("➕ Weitere Person hinzufügen"):
    naechste = max((p["id"] for p in aktualisiert), default=0) + 1
    st.session_state["personen"] = aktualisiert + [
        {"id": naechste, "alter": 8, "unfall": "MIT-UNF", "kosten": 500}
    ]
    st.rerun()

kinder = [p for p in aktualisiert if zielgruppe_fuer_alter(p["alter"]) == "Kinder"]
ergebnisse = []
for nummer, person in enumerate(aktualisiert, start=1):
    zielgruppe = zielgruppe_fuer_alter(person["alter"])
    if zielgruppe == "Kinder":
        position = kinder.index(person) + 1
        stufen = erlaubte_kinderstufen(position, len(kinder))
    else:
        stufen = ("K1",)

    with st.expander(
        f"{nummer}. {zielgruppe}, {person['alter']} Jahre – "
        f"{chf(person['kosten'])} CHF Krankheitskosten",
        expanded=len(aktualisiert) == 1,
    ):
        if zielgruppe == "Kinder" and len(kinder) > 1:
            st.caption(
                f"Kind {position} von {len(kinder)} – erreichbare Tarifstufen: "
                f"{', '.join(f'{s} ({KINDER_UNTERGRUPPEN[s]})' for s in stufen)}."
            )
        ergebnis = person_ansicht(
            roh, wohnort[0], wohnort[1], zielgruppe, {zielgruppe: person["unfall"]},
            tariftypen, stufen, umweltabgabe, person["kosten"], person["id"],
        )
    if ergebnis:
        ergebnisse.append(ergebnis)

haushalt_summe(ergebnisse, len(kinder))
