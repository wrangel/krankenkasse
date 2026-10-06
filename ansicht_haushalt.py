"""Die Summe über alle Personen."""

import pandas as pd
import streamlit as st

from basis import chf
from constants import KINDER


def haushalt_summe(
    ergebnisse: list[dict], anzahl_kinder: int, gemeinsam: dict | None = None
) -> None:
    """Die Summe über alle Personen - das, wonach am Ende gefragt ist."""
    if not ergebnisse:
        return

    kinder_einzeln = sum(
        e["jahreskosten"] for e in ergebnisse if e["zielgruppe"] == KINDER
    )
    uebrige = sum(
        e["jahreskosten"] for e in ergebnisse if e["zielgruppe"] != KINDER
    )
    # Für die Kinder gilt, was günstiger ist: jedes Kind frei zum Normaltarif,
    # oder alle zusammen bei einem Versicherer mit Geschwisterrabatt.
    kinder_gewaehlt = (
        min(kinder_einzeln, gemeinsam["total"]) if gemeinsam else kinder_einzeln
    )
    gesamt = uebrige + kinder_gewaehlt
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

    if gemeinsam and gemeinsam.get("unbekannte_stufen"):
        st.warning(
            f"Die Prämiendaten führen für Kinder die Tarifstufe(n) "
            f"**{', '.join(gemeinsam['unbekannte_stufen'])}**, deren Bedingungen "
            f"hier nicht bekannt sind. Sie bleiben in der Rechnung unberücksichtigt – "
            f"der Geschwisterrabatt könnte also höher ausfallen als unten gezeigt."
        )

    if gemeinsam:
        ersparnis = kinder_einzeln - gemeinsam["total"]
        stufen = ", ".join(k["stufe"] for k in gemeinsam["je_kind"])
        if ersparnis > 0:
            st.info(
                f"**Geschwisterrabatt: {chf(ersparnis)} CHF pro Jahr – aber nur bei "
                f"einem gemeinsamen Versicherer.**\n\n"
                f"- Jedes Kind einzeln beim für es günstigsten Anbieter, ohne "
                f"Rabatt: **{chf(kinder_einzeln)} CHF**\n"
                f"- Alle {anzahl_kinder} Kinder bei **{gemeinsam['versicherer']} – "
                f"{gemeinsam['tarif']}**, Tarifstufen {stufen}: "
                f"**{chf(gemeinsam['total'])} CHF**\n\n"
                f"K3, K4 und K5 gelten nur für Kinder derselben Familie beim "
                f"gleichen Versicherer. Rabatt und freie Wahl pro Kind schliessen "
                f"sich also aus. Oben eingerechnet ist die günstigere Variante.",
                icon="👪",
            )
        else:
            st.info(
                f"**Ein gemeinsamer Versicherer für die Kinder lohnt sich hier "
                f"nicht.** Jedes Kind einzeln zum günstigsten Anbieter kostet "
                f"{chf(kinder_einzeln)} CHF, alle zusammen bei "
                f"{gemeinsam['versicherer']} {chf(gemeinsam['total'])} CHF.",
                icon="👪",
            )

    uebersicht = pd.DataFrame(
        [
            {
                # Nummer und Altersklasse getrennt: "1. Erwachsene" liest sich wie
                # eine Person weiblichen Geschlechts, gemeint ist aber die Klasse.
                "Nr.": i,
                "Altersklasse": e["zielgruppe"],
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
            "Nr.": st.column_config.NumberColumn(format="%d", width="small"),
            "Franchise": st.column_config.NumberColumn(format="%d", width="small"),
            "Kosten/Jahr": st.column_config.NumberColumn(format="%.0f", width="small"),
            "Kosten/Monat": st.column_config.NumberColumn(format="%.2f", width="small"),
        },
    )

    # Der ganze Haushalt als CSV - mit einer Summenzeile, damit die Datei für sich
    # steht und nicht erst wieder zusammengezählt werden muss.
    summenzeile = pd.DataFrame(
        [{
            "Nr.": None,
            "Altersklasse": "Total",
            "Ort": "",
            "Franchise": None,
            "Versicherer": "",
            "Tarif": "",
            "Kosten/Jahr": round(gesamt),
            "Kosten/Monat": round(gesamt / 12, 2),
        }]
    )
    st.download_button(
        "Haushalt als CSV",
        pd.concat([uebersicht, summenzeile], ignore_index=True)
        .to_csv(index=False)
        .encode("utf-8"),
        file_name="haushalt.csv",
        mime="text/csv",
    )

    if anzahl_kinder >= 2:
        st.caption(
            "Zusätzlich begrenzt Art. 93 Abs. 3 KVV die Kostenbeteiligung aller "
            "Kinder beim gleichen Versicherer auf das Zweifache des Höchstbetrages "
            "je Kind – diese Deckelung ist oben **nicht** berücksichtigt, die reale "
            "Belastung kann also tiefer ausfallen."
        )


# Ein Klick ins Diagramm merkt den Wert vor; angewendet wird er hier, bevor die
