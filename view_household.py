"""The total across all people."""

import pandas as pd
import streamlit as st

from common import chf, chf_table, fit_width, header
from constants import CHILDREN, noticeable_saving
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
        # Each child's own cheapest offer already at the recommended insurer:
        # then there is nothing to choose - staying there together gets the
        # sibling tier anyway. "Each child separately, without discount" is
        # not an option anyone has, so it is not offered as one.
        same_insurer = all(
            r["insurer"] == shared["insurer"]
            for r in results if r["age_group"] == CHILDREN
        )
        if saving > 0.5:
            key = ("household.sibling_automatic" if same_insurer
                   else "household.sibling_discount")
            message = t(key,
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
        elif saving < -0.5:
            # Only when the children's own cheapest offers are with different
            # insurers - otherwise one insurer can never cost more. Equal
            # amounts need no box at all.
            st.info(
                t("household.sibling_not_worth",
                  separate=chf(children_separately), insurer=shared["insurer"],
                  total=chf(shared["total"])),
                icon="👪",
            )

    # Children placed together with one insurer (the box above) are compared
    # with that recommendation; their own best offers would contradict it.
    children_shared = bool(shared) and shared["total"] < children_separately

    def switch(r: dict) -> str:
        """Whether leaving today's contract pays, for the Wechsel column."""
        saving = r.get("switch_saving")
        if children_shared and r["age_group"] == CHILDREN:
            # Against the shared recommendation, not the child's own best.
            saving = shared.get("switch_by_id", {}).get(r.get("id"))
        if saving is None:
            return "–"
        if saving < noticeable_saving:
            return t("household.switch_no")
        return t("household.switch_saves", saving=chf(saving))

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
                # Per year only: the monthly figure for the whole household is
                # in the metric above, and a second money column per row
                # next to the yearly saving read as a third kind of amount.
                "Kosten/Jahr": round(r["annual_costs"]),
                "Wechsel": switch(r),
            }
            for i, r in enumerate(results, start=1)
        ]
    )
    st.dataframe(
        chf_table(overview, {"Franchise": 0, "Kosten/Jahr": 0}),
        hide_index=True,
        width="content",
        column_config={
            "Nr.": header("Nr.", kind=st.column_config.NumberColumn,
                          format="%d", alignment="left"),
            "Altersklasse": header("Altersklasse"),
            "Ort": header("Ort"),
            "Franchise": header("Franchise", kind=st.column_config.NumberColumn),
            "Versicherer": header("Versicherer", width=fit_width(
                overview["Versicherer"], t("col.Versicherer"))),
            "Tarif": header("Tarif", width=fit_width(
                overview["Tarif"], t("col.Tarif"))),
            "Kosten/Jahr": header("Kosten/Jahr",
                                        kind=st.column_config.NumberColumn),
            # Amounts, so right-aligned like the other money columns, even
            # though "nein" and "–" make it a text column.
            "Wechsel": header("Wechsel", kind=st.column_config.TextColumn,
                              alignment="right"),
        },
    )
    if any(r.get("switch_saving") is not None for r in results):
        st.caption(t("household.switch_note", threshold=noticeable_saving))

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
            "Wechsel": "",
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
