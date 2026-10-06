"""Die Summe über alle Personen."""

import pandas as pd
import streamlit as st

from basis import chf


def haushalt_summe(
    ergebnisse: list[dict], anzahl_kinder: int, gemeinsam: dict | None = None
) -> None:
    """Die Summe über alle Personen - das, wonach am Ende gefragt ist."""
    if not ergebnisse:
        return

    kinder_einzeln = sum(
        e["jahreskosten"] for e in ergebnisse if e["zielgruppe"] == "Kinder"
    )
    uebrige = sum(
        e["jahreskosten"] for e in ergebnisse if e["zielgruppe"] != "Kinder"
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

    if gemeinsam:
        st.subheader("Geschwisterrabatt")
        ersparnis = kinder_einzeln - gemeinsam["total"]
        stufen = ", ".join(k["stufe"] for k in gemeinsam["je_kind"])
        links, rechts = st.columns(2)
        links.metric(
            "Jedes Kind einzeln, ohne Rabatt", f"{chf(kinder_einzeln)} CHF"
        )
        rechts.metric(
            "Alle Kinder beim gleichen Versicherer",
            f"{chf(gemeinsam['total'])} CHF",
            delta=f"{-ersparnis:,.0f} CHF".replace(",", "'"),
            delta_color="inverse" if ersparnis > 0 else "normal",
        )
        if ersparnis > 0:
            st.caption(
                f"**{gemeinsam['versicherer']} – {gemeinsam['tarif']}** für alle "
                f"{anzahl_kinder} Kinder, Tarifstufen {stufen}: "
                f"**{chf(ersparnis)} CHF pro Jahr günstiger**, als jedes Kind "
                f"einzeln zum günstigsten Anbieter zu versichern. Der Rabatt setzt "
                f"voraus, dass alle Kinder beim **gleichen** Versicherer sind – "
                f"deshalb lässt er sich nicht mit der freien Wahl pro Kind "
                f"kombinieren. In der Summe oben ist die günstigere Variante "
                f"eingerechnet."
            )
        else:
            st.caption(
                f"Ein gemeinsamer Vertrag bringt hier nichts: Jedes Kind einzeln "
                f"zum günstigsten Anbieter kommt gleich teuer oder günstiger."
            )
        st.caption(
            f"Zusätzlich begrenzt Art. 93 Abs. 3 KVV die Kostenbeteiligung aller "
            f"Kinder beim gleichen Versicherer auf das Zweifache des Höchstbetrages "
            f"je Kind – diese Deckelung ist oben **nicht** berücksichtigt, die reale "
            f"Belastung kann also tiefer ausfallen."
        )


# Ein Klick ins Diagramm merkt den Wert vor; angewendet wird er hier, bevor die
