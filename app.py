import json

import altair as alt
import pandas as pd
import streamlit as st

from constants import (
    KINDER_UNTERGRUPPEN,
    hoechstgrenze_selbstbehalt,
    selbstbehalt_anteil,
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

# Die Auswahlchips der Mehrfachauswahl kommen in der Signalfarbe des Themes. Die
# gehört den Knöpfen, die etwas auslösen - eine Liste gewählter Tarifmodelle ist
# eine Angabe, keine Warnung. Deshalb neutral grau.
st.markdown(
    """
    <style>
      [data-testid="stMultiSelectTagsContainer"] span[data-tag] {
          background-color: rgba(250, 250, 250, 0.14) !important;
          color: inherit !important;
      }
      [data-testid="stMultiSelectTagsContainer"] span[data-tag] svg {
          fill: currentColor !important;
      }
      /* Hinzufügen grün, Entfernen rot - die Farbe soll sagen, was passiert.
         Streamlit hängt den Widget-Schlüssel als Klasse st-key-… an den
         Container, das ist der einzige verlässliche Haken auf einen bestimmten
         Knopf. */
      .st-key-person_hinzu button {
          background-color: #1b7f4d !important;
          border-color: #1b7f4d !important;
          color: #ffffff !important;
      }
      .st-key-person_hinzu button:hover {
          background-color: #166b41 !important;
      }
      [class*="st-key-weg_"] button {
          background-color: transparent !important;
          border-color: #c2341f !important;
          color: #e06552 !important;
      }
      [class*="st-key-weg_"] button:hover {
          background-color: rgba(194, 52, 31, 0.15) !important;
      }
      /* Der gewählte Radioknopf, aus demselben Grund neutral. Nur der Kreis
         selbst: "div div" träfe auch die Beschriftung daneben. */
      [data-testid="stRadioOption"][data-selected="true"] > div > div:first-child {
          background-color: rgba(250, 250, 250, 0.85) !important;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

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


def wohnort_waehlen(schluessel: int, spalte=None) -> tuple[str, str, str] | None:
    """Fragt die Postleitzahl ab und schlägt Kanton und Prämienregion nach.

    Die Prämienregion bestimmt die Prämie mit, aber kaum jemand weiss, in welcher
    er wohnt - die Postleitzahl weiss dagegen jeder. Rund jede zwölfte PLZ liegt
    allerdings in mehreren Regionen oder Kantonen; dann wird zusätzlich nach der
    Ortschaft gefragt, statt stillschweigend die erste zu nehmen.

    Gibt (Kanton, Region, Beschriftung) zurück oder None, wenn nichts passt.
    """
    ziel = spalte if spalte is not None else st
    zuordnung = regionen_nach_plz()
    if not zuordnung:
        ziel.error(
            "Die Zuordnung der Postleitzahlen fehlt. Einmalig erzeugen mit "
            "`python refresh_regionen.py`."
        )
        return None

    plz = ziel.text_input(
        "Postleitzahl", value="8001", max_chars=4, key=f"plz_{schluessel}"
    ).strip()
    eintraege = zuordnung.get(plz)
    if not eintraege:
        if plz:
            ziel.warning(f"Zur PLZ {plz} ist keine Prämienregion bekannt.")
        return None

    varianten = {(e["kanton"], e["region"]) for e in eintraege}
    if len(varianten) > 1:
        gewaehlt = ziel.selectbox(
            "Ortschaft",
            eintraege,
            format_func=lambda e: f"{e['ort']} ({e['kanton']}, Region {e['region']})",
            key=f"ort_{schluessel}",
            help="Diese Postleitzahl liegt in mehreren Prämienregionen.",
        )
    else:
        gewaehlt = eintraege[0]

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


def person_eckwerte(
    roh, kanton, region, zielgruppe, unfalldeckung, tariftypen,
    kinder_untergruppen, umweltabgabe, erwartete_kosten,
) -> dict | None:
    """Die Eckwerte einer Person, ohne etwas zu zeichnen.

    Gebraucht für eingeklappte Personen: Die Haushaltssumme muss alle enthalten,
    auch die, deren Bericht gerade zugeklappt ist - sonst ändert sich der
    Gesamtbetrag, bloss weil jemand einen Abschnitt zuklappt.
    """
    daten = get_data(
        roh, kanton=kanton, region=region, zielgruppen=(zielgruppe,),
        unfalldeckung=unfalldeckung, kinder_untergruppen=tuple(kinder_untergruppen),
        tariftypen=tuple(tariftypen) if tariftypen else None,
    )
    beste = beste_praemien(daten)
    if beste.empty:
        return None
    ergebnisse = berechne_kipppunkt(
        beste, umweltabgabe, max(maximale_krankenkosten, int(erwartete_kosten) + 2000)
    )
    if not ergebnisse:
        return None

    e = ergebnisse[0]
    bei_erwartung = e.kosten.loc[erwartete_kosten]
    beste_franchise = int(bei_erwartung.idxmin())
    angebot = (
        daten[(daten["Zielgruppe"] == zielgruppe) & (daten["Franchise"] == beste_franchise)]
        .nsmallest(1, "Prämie")
    )
    if angebot.empty:
        return None
    zeile = angebot.iloc[0]
    return {
        "zielgruppe": zielgruppe,
        "franchise": beste_franchise,
        "jahreskosten": float(bei_erwartung.min()),
        "versicherer": zeile["Versicherername"],
        "tarif": zeile["Tarifbezeichnung"],
        "praemie_jahr": float(zeile["Prämie"]) * 12,
    }


def person_ansicht(
    roh, kanton, region, zielgruppe, unfalldeckung, tariftypen,
    kinder_untergruppen, umweltabgabe, erwartete_kosten, schluessel, jetzt=None,
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
    praemienjahr = int(roh["Geschäftsjahr"].max())
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
    kurven = kurven[kurven["Krankheitskosten"].between(fenster_von, fenster_bis)]

    # Ausdünnen fürs Zeichnen. Die Kurven sind stückweise linear, jeder Franken
    # einzeln ist also nichts als Datenvolumen: Im Fenster sind das rund 23'000
    # Punkte oder 900 KB JSON - pro Diagramm, pro Person, bei jedem Rerun. Bei
    # 25er-Schritten bleiben 36 KB bei gleichem Bild.
    #
    # Die Knickstellen müssen aber erhalten bleiben, sonst wird die Kurve an den
    # interessanten Stellen abgeschnitten: dort, wo die Franchise ausgeschöpft
    # ist, wo der Selbstbehalt seinen Deckel erreicht, am Kipppunkt und an den
    # Fensterrändern.
    obergrenze = hoechstgrenze_selbstbehalt[zielgruppe]
    knicke = {fenster_von, fenster_bis, int(erwartete_kosten)}
    if e.kipppunkt is not None:
        knicke.update({e.kipppunkt - 1, e.kipppunkt})
    for franchise in e.kosten.columns:
        knicke.add(int(franchise))
        knicke.add(int(franchise + obergrenze / selbstbehalt_anteil))
    schritt = max(1, (fenster_bis - fenster_von) // 400)
    behalten = kurven["Krankheitskosten"].isin(knicke) | (
        kurven["Krankheitskosten"] % schritt == 0
    )
    kurven = kurven[behalten]

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
        diagramm + treffer, width="stretch", on_select="rerun",
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
        width="stretch",
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
    # Vollständige Rangliste für diese Franchise - gezeigt werden die sieben
    # günstigsten, aber der heutige Vertrag soll auch dann auftauchen, wenn er
    # weiter hinten liegt. Sonst sieht man nur, was es gäbe, nie, wo man steht.
    rangliste = (
        zielgruppe_daten[zielgruppe_daten["Franchise"] == beste_franchise]
        .sort_values("Prämie")
        .reset_index(drop=True)
    )
    rangliste["Rang"] = rangliste.index + 1

    jetzt_zeile, jetzt_rang = None, None
    if jetzt:
        treffer = rangliste[
            (rangliste["Versicherername"] == jetzt[0])
            & (rangliste["Tarifbezeichnung"] == jetzt[1])
        ]
        if not treffer.empty:
            jetzt_zeile = treffer.iloc[0]
            jetzt_rang = int(jetzt_zeile["Rang"])

    gezeigt = rangliste.head(7)
    if jetzt_rang is not None and jetzt_rang > 7:
        gezeigt = pd.concat([gezeigt, treffer], ignore_index=True)

    angebote = gezeigt[
        ["Rang", "Versicherername", "Tarifbezeichnung", "Tariftyp", "Prämie"]
    ].reset_index(drop=True)
    if angebote.empty:
        st.info("Für diese Franchise gibt es keine Angebote.")
    else:
        angebote = angebote.rename(
            columns={"Versicherername": "Versicherer", "Tarifbezeichnung": "Tarif",
                     "Tariftyp": "Typ"}
        )
        angebote["Prämie/Jahr"] = (angebote["Prämie"] * 12).round(0)
        angebote = _mit_abstand(angebote, "Prämie/Jahr", "Mehrkosten/Jahr")
        angebote["Prämie/Monat"] = angebote["Prämie"].round(2)
        angebote["Typ"] = angebote["Typ"].map(TARIFTYPEN_KURZ)
        spalten = ["Rang", "Versicherer", "Tarif", "Typ", "Prämie/Jahr",
                   "Mehrkosten/Jahr", "Prämie/Monat"]
        # Die Markierungsspalte nur anlegen, wenn es etwas zu markieren gibt -
        # sonst steht eine leere Spalte da und fragt, was ihr fehlt.
        markierung = [
            "◀ jetziger Versicherer"
            if jetzt and v == jetzt[0] and ta == jetzt[1]
            else ""
            for v, ta in zip(gezeigt["Versicherername"], gezeigt["Tarifbezeichnung"])
        ]
        if any(markierung):
            angebote[""] = markierung
            spalten.append("")
        angebote = angebote[spalten]

        st.dataframe(
            angebote,
            hide_index=True,
            width="stretch",
            column_config={
                "Rang": st.column_config.NumberColumn(format="%d", width="small"),
                "Versicherer": st.column_config.TextColumn(width="medium"),
                "Tarif": st.column_config.TextColumn(width="small"),
                "Typ": st.column_config.TextColumn(width="small"),
                "Prämie/Jahr": st.column_config.NumberColumn(format="%.0f", width="small"),
                "Mehrkosten/Jahr": st.column_config.NumberColumn(
                    format="%.0f", width="small"
                ),
                "Prämie/Monat": st.column_config.NumberColumn(
                    format="%.2f", width="small"
                ),
                "": st.column_config.TextColumn(width="medium"),
            },
        )

        if jetzt and jetzt_rang is None:
            st.caption(
                f"**{jetzt[0]} – {jetzt[1]}** führt für die Franchise "
                f"{beste_franchise} CHF kein Angebot, das zu den gewählten "
                f"Tarifmodellen passt."
            )
        elif jetzt_rang == 1:
            st.success(
                f"Du hast auch {praemienjahr} den günstigsten Anbieter für dieses "
                f"Szenario: **{jetzt[0]} – {jetzt[1]}**. Ein Wechsel würde nichts "
                f"sparen."
            )
        elif jetzt_rang is not None:
            mehr = (float(jetzt_zeile["Prämie"]) - float(rangliste.iloc[0]["Prämie"])) * 12
            st.info(
                f"Dein heutiger Vertrag **{jetzt[0]} – {jetzt[1]}** liegt auf Rang "
                f"{jetzt_rang} von {len(rangliste)}. Der günstigste Anbieter für "
                f"dieses Szenario kostet **{chf(mehr)} CHF pro Jahr weniger**."
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


def anbieter_und_modelle(
    roh, kanton: str, region: str, zielgruppe: str, unfall: str
) -> dict[str, list[str]]:
    """Versicherer am Wohnort und ihre Tarifbezeichnungen, für die Auswahl."""
    daten = get_data(
        roh, kanton=kanton, region=region, zielgruppen=(zielgruppe,),
        unfalldeckung={zielgruppe: unfall},
        kinder_untergruppen=tuple(KINDER_UNTERGRUPPEN),
    )
    if daten.empty:
        return {}
    gruppiert = (
        daten.groupby("Versicherername")["Tarifbezeichnung"]
        .apply(lambda s: sorted(s.unique()))
        .to_dict()
    )
    return dict(sorted(gruppiert.items()))


def person_formular(person: dict, anzahl_personen: int, roh) -> dict | None:
    """Alle Angaben einer Person. Gibt den aktualisierten Eintrag zurück.

    Wohnort und Tarifmodelle stehen hier statt in einer gemeinsamen Seitenleiste:
    Ein Haushalt kann über Gemeindegrenzen verteilt sein, und wer für sich die
    freie Arztwahl will, will sie nicht zwingend auch für alle anderen.
    """
    kennung = person["id"]
    oben = st.columns([3, 2, 3, 3])

    wohnort = wohnort_waehlen(kennung, oben[0])

    alter = oben[1].number_input(
        "Alter", min_value=0, max_value=120, value=int(person["alter"]), step=1,
        key=f"alter_{kennung}",
    )
    zielgruppe = zielgruppe_fuer_alter(int(alter))

    unfall = oben[2].radio(
        "Unfalldeckung",
        ["MIT-UNF", "OHN-UNF"],
        index=1 if zielgruppe == "Erwachsene" else 0,
        format_func=lambda u: "mit" if u == "MIT-UNF" else "ohne",
        horizontal=True,
        key=f"unfall_{kennung}",
        help="Wer mindestens acht Stunden pro Woche bei demselben Arbeitgeber "
        "arbeitet, ist dort gegen Unfall versichert.",
    )

    schluessel = f"kosten_{kennung}"
    st.session_state.setdefault(schluessel, int(person["kosten"]))
    kosten = oben[3].number_input(
        "Erwartete Krankheitskosten pro Jahr (CHF)",
        min_value=0, step=100, key=schluessel,
        help="Der wichtigste Wert neben dem Alter. Arztbesuche, Medikamente, "
        "Therapien – alles, was über die Grundversicherung läuft.",
    )

    tariftypen = st.multiselect(
        "Tarifmodelle",
        list(TARIFTYPEN),
        default=list(TARIFTYPEN),
        format_func=lambda m: TARIFTYPEN[m],
        key=f"modelle_{kennung}",
        help="Das Standardmodell lässt die Arztwahl frei; die übrigen schränken sie "
        "ein und sind dafür günstiger.",
    )

    # Der heutige Vertrag - damit die Auswertung sagen kann, ob sich ein Wechsel
    # überhaupt lohnt, statt nur das theoretisch Günstigste zu zeigen.
    jetzt_versicherer, jetzt_modell = None, None
    if wohnort is not None:
        angebot = anbieter_und_modelle(
            roh, wohnort[0], wohnort[1], zielgruppe, unfall
        )
        if angebot:
            heute = st.columns(2)
            jetzt_versicherer = heute[0].selectbox(
                "Jetziger Versicherer",
                [None, *angebot],
                format_func=lambda v: "– noch keiner / unbekannt –" if v is None else v,
                key=f"jetzt_vers_{kennung}",
                help="Optional. Damit zeigt die Tabelle unten, auf welchem Rang dein "
                "heutiger Vertrag liegt.",
            )
            if jetzt_versicherer:
                modelle = angebot[jetzt_versicherer]
                jetzt_modell = heute[1].selectbox(
                    "Jetziges Modell", modelle, key=f"jetzt_mod_{kennung}"
                )

    if wohnort is None:
        st.warning("Ohne gültige Postleitzahl lässt sich für diese Person nichts rechnen.")

    # Der Löschknopf stand bisher in derselben Zeile wie die Tarifmodelle, direkt
    # neben deren Lösch- und Aufklapp-Symbolen - ein Fehlgriff dort entfernt die
    # ganze Person, ohne Rückfrage. Jetzt steht er unten rechts für sich.
    if anzahl_personen > 1:
        _, rechts_unten = st.columns([5, 1])
        if rechts_unten.button("Person entfernen", key=f"weg_{kennung}"):
            st.session_state["personen"] = [
                e for e in st.session_state["personen"] if e["id"] != kennung
            ]
            st.rerun()

    return {
        "id": kennung,
        "alter": int(alter),
        "unfall": unfall,
        "kosten": int(kosten),
        "wohnort": wohnort,
        "tariftypen": tariftypen,
        "zielgruppe": zielgruppe,
        "jetzt": (jetzt_versicherer, jetzt_modell) if jetzt_versicherer else None,
    }


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
                "Ort": e["ort"],
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
        width="stretch",
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

roh = praemien(7)

st.title("Welche Franchise lohnt sich?")
st.caption(
    "Die Grundversicherung bietet mehrere Franchisen zur Auswahl. Diese App rechnet "
    "für jede Person nach, welche davon überhaupt je die günstigste ist und ab welchen "
    "jährlichen Krankheitskosten es von der einen zur anderen kippt."
)
st.info(
    f"**Prämienjahr {int(roh['Geschäftsjahr'].max())}** · Datenquelle: BAG-Prämiendaten "
    f"über opendata.swiss · Rückerstattung Umweltabgaben "
    f"**{umweltabgabe_standard * 12:.2f} CHF pro Jahr** "
    f"({umweltabgabe_standard:.2f} pro Monat), für alle Versicherten gleich und bereits "
    f"von den Prämien abgezogen.",
    icon="ℹ️",
)

personen = st.session_state["personen"]

# Wie viele Kinder im Haushalt leben, muss feststehen, bevor die erste Person
# gezeichnet wird - davon hängt ab, welche Tarifstufen einem Kind offenstehen.
# Die Alter stehen schon in session_state, weil Streamlit die Werte der Eingabe-
# felder über ihren Schlüssel hält; für eine eben hinzugefügte Person gibt es den
# Schlüssel noch nicht, dann gilt ihr Startwert.
def _alter_von(eintrag: dict) -> int:
    return int(st.session_state.get(f"alter_{eintrag['id']}", eintrag["alter"]))


kinder_ids = [
    e["id"] for e in personen if zielgruppe_fuer_alter(_alter_von(e)) == "Kinder"
]

aktualisiert = []
ergebnisse = []
for nummer, person in enumerate(personen, start=1):
    with st.container(border=True):
        kopf = st.columns([6, 2])
        kopf[0].markdown(f"**{nummer}. Person**")

        # Ein benannter Knopf statt nur eines Pfeils: Er sagt, was er tut, und
        # steht immer an derselben Stelle - ob der Bericht gerade offen ist oder
        # nicht.
        offen_schluessel = f"offen_{person['id']}"
        offen = st.session_state.setdefault(offen_schluessel, nummer == 1)
        if kopf[1].button(
            "Einklappen" if offen else "Ausklappen",
            key=f"klapp_{person['id']}",
            width="stretch",
        ):
            st.session_state[offen_schluessel] = not offen
            st.rerun()

        eintrag = person_formular(person, len(personen), roh)
        aktualisiert.append(eintrag)

        if eintrag["wohnort"] is None:
            continue

        zielgruppe = eintrag["zielgruppe"]
        if zielgruppe == "Kinder" and person["id"] in kinder_ids:
            position = kinder_ids.index(person["id"]) + 1
            stufen = erlaubte_kinderstufen(position, len(kinder_ids))
            if offen and len(kinder_ids) > 1:
                st.caption(
                    f"Kind {position} von {len(kinder_ids)} – erreichbare "
                    f"Tarifstufen: "
                    f"{', '.join(f'{s} ({KINDER_UNTERGRUPPEN[s]})' for s in stufen)}."
                )
        else:
            stufen = ("K1",)

        if offen:
            st.markdown("---")
            ergebnis = person_ansicht(
                roh, eintrag["wohnort"][0], eintrag["wohnort"][1], zielgruppe,
                {zielgruppe: eintrag["unfall"]}, eintrag["tariftypen"], stufen,
                umweltabgabe_standard, eintrag["kosten"], person["id"], eintrag["jetzt"],
            )
        else:
            ergebnis = person_eckwerte(
                roh, eintrag["wohnort"][0], eintrag["wohnort"][1], zielgruppe,
                {zielgruppe: eintrag["unfall"]}, eintrag["tariftypen"], stufen,
                umweltabgabe_standard, eintrag["kosten"],
            )
        if ergebnis:
            ergebnis["ort"] = eintrag["wohnort"][2].split(" (")[0]
            ergebnisse.append(ergebnis)

st.session_state["personen"] = [
    {k: v for k, v in p.items() if k in {"id", "alter", "unfall", "kosten"}}
    for p in aktualisiert
]

if st.button("➕ Weitere Person hinzufügen", key="person_hinzu", width="stretch"):
    naechste = max((p["id"] for p in aktualisiert), default=0) + 1
    st.session_state["personen"] = st.session_state["personen"] + [
        {"id": naechste, "alter": 8, "unfall": "MIT-UNF", "kosten": 500}
    ]
    # Die neue Person aufklappen, die übrigen zu - sonst steht man vor einer
    # Seite voller offener Berichte und sieht nicht, was eben dazugekommen ist.
    for e in aktualisiert:
        st.session_state[f"offen_{e['id']}"] = False
    st.session_state[f"offen_{naechste}"] = True
    st.rerun()

haushalt_summe(ergebnisse, len(kinder_ids))

st.markdown("---")
spalte_links, spalte_rechts = st.columns([3, 1])
spalte_links.caption(
    "Die Prämiendaten werden beim ersten Aufruf geladen und sieben Tage "
    "zwischengespeichert."
)
if spalte_rechts.button("Prämiendaten neu laden"):
    st.cache_data.clear()
    praemien(0)
    st.rerun()
