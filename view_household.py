"""The total across all people."""

import pandas as pd
import streamlit as st

from common import chf, header
from constants import CHILDREN
from i18n import t


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
    st.header(t("household.heading"))

    columns = st.columns(3)
    columns[0].metric(t("household.per_year"), f"{chf(total)} CHF")
    columns[1].metric(t("household.per_month"), f"{chf(total / 12, 2)} CHF")
    columns[2].metric(t("household.people"), str(len(results)))
    st.caption(t("household.caption", premiums=chf(premiums)))

    if shared and shared.get("unknown_tiers"):
        st.warning(
            t("household.unknown_tiers",
              tiers=", ".join(shared["unknown_tiers"]))
        )

    if shared:
        saving = children_separately - shared["total"]
        tiers = ", ".join(c["tier"] for c in shared["per_child"])
        if saving > 0:
            message = t("household.sibling_discount",
                        saving=chf(saving), separate=chf(children_separately),
                        count=child_count, insurer=shared["insurer"],
                        tariff=shared["tariff"], tiers=tiers,
                        total=chf(shared["total"]))
            # Part of the saving can be the statutory family cap rather than a
            # discount - say so, and under which law, since it differs between
            # no deductible (KVG) and a chosen one (KVV).
            if shared.get("family_cap_saving", 0) > 0:
                law = ("law.family_cap_no_deductible"
                       if shared["per_child"][0]["deductible"] == 0
                       else "law.family_cap_chosen_deductible")
                message += "\n\n" + t("household.family_cap_applied",
                                       cap=chf(shared["family_cap"]), law=t(law),
                                       saving=chf(shared["family_cap_saving"]))
            st.info(message, icon="👪")
        else:
            st.info(
                t("household.sibling_not_worth",
                  separate=chf(children_separately), insurer=shared["insurer"],
                  total=chf(shared["total"])),
                icon="👪",
            )

    overview = pd.DataFrame(
        [
            {
                # Number and age class kept apart: "1. Erwachsene" reads like a
                # female person, whereas the class is what is meant.
                "Nr.": i,
                "Altersklasse": t(f'age_class.{r["age_group"]}'),
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
            "Nr.": header("Nr.", kind=st.column_config.NumberColumn,
                          format="%d", width="small", alignment="left"),
            "Altersklasse": header("Altersklasse"),
            "Ort": header("Ort"),
            "Franchise": header("Franchise", kind=st.column_config.NumberColumn,
                                format="%d", width="small"),
            "Versicherer": header("Versicherer"),
            "Tarif": header("Tarif"),
            "Kosten/Jahr": header("Kosten/Jahr",
                                  kind=st.column_config.NumberColumn,
                                  format="%.0f", width="small"),
            "Kosten/Monat": header("Kosten/Monat",
                                   kind=st.column_config.NumberColumn,
                                   format="%.2f", width="small"),
        },
    )

    # The whole household as CSV - with a total row, so the file stands on its
    # own and does not have to be added up again.
    total_row = pd.DataFrame(
        [{
            "Nr.": None,
            "Altersklasse": t("household.total_row"),
            "Ort": "",
            "Franchise": None,
            "Versicherer": "",
            "Tarif": "",
            "Kosten/Jahr": round(total),
            "Kosten/Monat": round(total / 12, 2),
        }]
    )
    st.download_button(
        t("household.csv_button"),
        pd.concat([overview, total_row], ignore_index=True)
        .to_csv(index=False)
        .encode("utf-8"),
        file_name="haushalt.csv",
        mime="text/csv",
    )
