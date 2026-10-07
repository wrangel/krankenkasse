"""The total across all people."""

import pandas as pd
import streamlit as st

from common import chf
from constants import CHILDREN


def household_total(
    results: list[dict], child_count: int, shared: dict | None = None
) -> None:
    """The total across all people - what the question comes down to in the end."""
    if not results:
        return

    children_separately = sum(
        r["annual_costs"] for r in results if r["age_group"] == CHILDREN
    )
    others = sum(r["annual_costs"] for r in results if r["age_group"] != CHILDREN)
    # For the children, whichever is cheaper applies: each child free to pick on
    # the standard tier, or all of them with one insurer on a sibling discount.
    children_chosen = (
        min(children_separately, shared["total"]) if shared else children_separately
    )
    total = others + children_chosen
    premiums = sum(r["annual_premium"] for r in results)

    st.markdown("---")
    st.header("Gesamtkosten des Haushalts")

    columns = st.columns(3)
    columns[0].metric("Pro Jahr", f"{chf(total)} CHF")
    columns[1].metric("Pro Monat", f"{chf(total / 12, 2)} CHF")
    columns[2].metric("Personen", str(len(results)))
    st.caption(
        f"Summe über alle Personen: Prämien ({chf(premiums)} CHF) plus Franchise und "
        f"Selbstbehalt bei den jeweils angegebenen Krankheitskosten, je zum "
        f"günstigsten Angebot."
    )

    if shared and shared.get("unknown_tiers"):
        st.warning(
            f"Die Prämiendaten führen für Kinder die Tarifstufe(n) "
            f"**{', '.join(shared['unknown_tiers'])}**, deren Bedingungen "
            f"hier nicht bekannt sind. Sie bleiben in der Rechnung unberücksichtigt – "
            f"der Geschwisterrabatt könnte also höher ausfallen als unten gezeigt."
        )

    if shared:
        saving = children_separately - shared["total"]
        tiers = ", ".join(c["tier"] for c in shared["per_child"])
        if saving > 0:
            st.info(
                f"**Geschwisterrabatt: {chf(saving)} CHF pro Jahr – aber nur bei "
                f"einem gemeinsamen Versicherer.**\n\n"
                f"- Jedes Kind einzeln beim für es günstigsten Anbieter, ohne "
                f"Rabatt: **{chf(children_separately)} CHF**\n"
                f"- Alle {child_count} Kinder bei **{shared['insurer']} – "
                f"{shared['tariff']}**, Tarifstufen {tiers}: "
                f"**{chf(shared['total'])} CHF**\n\n"
                f"K3, K4 und K5 gelten nur für Kinder derselben Familie beim "
                f"gleichen Versicherer. Rabatt und freie Wahl pro Kind schliessen "
                f"sich also aus. Oben eingerechnet ist die günstigere Variante.",
                icon="👪",
            )
        else:
            st.info(
                f"**Ein gemeinsamer Versicherer für die Kinder lohnt sich hier "
                f"nicht.** Jedes Kind einzeln zum günstigsten Anbieter kostet "
                f"{chf(children_separately)} CHF, alle zusammen bei "
                f"{shared['insurer']} {chf(shared['total'])} CHF.",
                icon="👪",
            )

    overview = pd.DataFrame(
        [
            {
                # Number and age class kept apart: "1. Erwachsene" reads like a
                # female person, whereas the class is what is meant.
                "Nr.": i,
                "Altersklasse": r["age_group"],
                "Ort": r["town"],
                "Franchise": r["deductible"],
                "Versicherer": r["insurer"],
                "Tarif": r["tariff"],
                "Kosten/Jahr": round(r["annual_costs"]),
                "Kosten/Monat": round(r["annual_costs"] / 12, 2),
            }
            for i, r in enumerate(results, start=1)
        ]
    )
    st.dataframe(
        overview,
        hide_index=True,
        width="stretch",
        column_config={
            "Nr.": st.column_config.NumberColumn(format="%d", width="small"),
            "Franchise": st.column_config.NumberColumn(format="%d", width="small"),
            "Kosten/Jahr": st.column_config.NumberColumn(format="%.0f", width="small"),
            "Kosten/Monat": st.column_config.NumberColumn(format="%.2f", width="small"),
        },
    )

    # The whole household as CSV - with a total row, so the file stands on its
    # own and does not have to be added up again.
    total_row = pd.DataFrame(
        [{
            "Nr.": None,
            "Altersklasse": "Total",
            "Ort": "",
            "Franchise": None,
            "Versicherer": "",
            "Tarif": "",
            "Kosten/Jahr": round(total),
            "Kosten/Monat": round(total / 12, 2),
        }]
    )
    st.download_button(
        "Haushalt als CSV",
        pd.concat([overview, total_row], ignore_index=True)
        .to_csv(index=False)
        .encode("utf-8"),
        file_name="haushalt.csv",
        mime="text/csv",
    )

    if child_count >= 2:
        st.caption(
            "Zusätzlich begrenzt Art. 93 Abs. 3 KVV die Kostenbeteiligung aller "
            "Kinder beim gleichen Versicherer auf das Zweifache des Höchstbetrages "
            "je Kind – diese Deckelung ist oben **nicht** berücksichtigt, die reale "
            "Belastung kann also tiefer ausfallen."
        )
