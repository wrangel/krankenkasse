"""The view of a single person: inputs, chart, tables.

person_form() takes the details, person_view() draws the report and
person_summary() returns the same figures without any user interface - for
people whose report is currently collapsed but who still belong in the
household total.

German text in this module is user-facing and stays until the translation layer
arrives. So do the DataFrame column labels, which are shown as table headers and
chart axes.
"""

import altair as alt
import pandas as pd
import streamlit as st

from common import age_group_for_age, chf, choose_location, with_gap_to_cheapest
from constants import (
    ADULTS,
    CHILD_SUBGROUPS,
    TARIFF_TYPES,
    TARIFF_TYPES_SHORT,
    coinsurance_cap,
    coinsurance_rate,
    min_cost_range,
)
from calculation import cheapest_premiums, compute_tipping_point, get_data


def person_summary(
    raw, canton, region, age_group, accident_cover, tariff_types,
    child_subgroups, environmental_rebate, expected_costs,
) -> dict | None:
    """The key figures for one person, without drawing anything.

    Needed for collapsed people: the household total has to include everyone,
    including those whose report is currently folded away - otherwise the total
    changes just because somebody closed a section.
    """
    data = get_data(
        raw, canton=canton, region=region, age_groups=(age_group,),
        accident_cover=accident_cover, child_subgroups=tuple(child_subgroups),
        tariff_types=tuple(tariff_types) if tariff_types else None,
    )
    cheapest = cheapest_premiums(data)
    if cheapest.empty:
        return None
    results = compute_tipping_point(
        cheapest, environmental_rebate, max(min_cost_range, int(expected_costs) + 2000)
    )
    if not results:
        return None

    r = results[0]
    at_expected = r.costs.loc[expected_costs]
    best_deductible = int(at_expected.idxmin())
    offer = data[
        (data["Zielgruppe"] == age_group) & (data["Franchise"] == best_deductible)
    ].nsmallest(1, "Prämie")
    if offer.empty:
        return None
    row = offer.iloc[0]
    return {
        "age_group": age_group,
        "deductible": best_deductible,
        "annual_costs": float(at_expected.min()),
        "insurer": row["Versicherername"],
        "tariff": row["Tarifbezeichnung"],
        "annual_premium": float(row["Prämie"]) * 12,
    }


def person_view(
    raw, canton, region, age_group, accident_cover, tariff_types,
    child_subgroups, environmental_rebate, expected_costs, key, current=None,
):
    """Draw one person and return their key figures for the household total."""
    data = get_data(
        raw,
        canton=canton,
        region=region,
        age_groups=(age_group,),
        accident_cover=accident_cover,
        child_subgroups=tuple(child_subgroups),
        tariff_types=tuple(tariff_types) if tariff_types else None,
    )
    cheapest = cheapest_premiums(data)
    if cheapest.empty:
        st.warning("Für diese Auswahl gibt es keine Prämien.")
        return None

    # The computation always covers a range that includes the costs entered -
    # otherwise a high value would fall outside the cost matrix.
    premium_year = int(raw["Geschäftsjahr"].max())
    cost_range = max(min_cost_range, int(expected_costs) + 2000)
    results = compute_tipping_point(cheapest, environmental_rebate, cost_range)
    if not results:
        st.warning("Für diese Auswahl lässt sich nichts berechnen.")
        return None
    r = results[0]

    # The top only states what holds at the costs entered. The tipping point
    # itself explains the dashed line in the chart and is therefore stated there.
    at_expected = r.costs.loc[expected_costs]
    best_deductible = int(at_expected.idxmin())
    left, right = st.columns(2)
    left.metric("Günstigste Franchise", f"{best_deductible} CHF")
    right.metric("Gesamtkosten pro Jahr", f"{chf(at_expected.min())} CHF")
    st.caption(
        "Prämien plus Franchise und Selbstbehalt, beim **günstigsten verfügbaren "
        "Angebot** – die Übersicht dazu steht weiter unten."
    )

    st.subheader("Kostenverlauf")
    curves = r.costs.reset_index().melt(
        id_vars="Krankheitskosten", var_name="Franchise", value_name="Jahreskosten"
    )
    dominated = set(r.never_optimal)
    curves["Rolle"] = [
        "nie optimal" if d in dominated else "kommt in Frage"
        for d in curves["Franchise"]
    ]
    # The deductible that is cheapest at the current costs is drawn in bold - so
    # you can see at a glance which curve is yours.
    curves["Auswahl"] = [
        "günstigste Wahl" if d == best_deductible else "andere"
        for d in curves["Franchise"]
    ]
    curves["Franchise"] = curves["Franchise"].astype(str)

    # A window rather than the whole range: what is shown is the neighbourhood
    # of the two vertical lines. A fixed margin around your own costs alone
    # would push the tipping point out of the picture as soon as the two sit far
    # apart - and so take away precisely the orientation it is there to give.
    margin = 2000
    anchors = [expected_costs] + (
        [r.tipping_point] if r.tipping_point is not None else []
    )
    window_from = max(0, min(anchors) - margin)
    window_to = min(cost_range, max(anchors) + margin)
    curves = curves[curves["Krankheitskosten"].between(window_from, window_to)]

    # Thin out for drawing. The curves are piecewise linear, so every single
    # franc is nothing but payload: within the window that is some 23,000 points
    # or 900 KB of JSON - per chart, per person, on every rerun. At steps of 25
    # that leaves 36 KB for the same picture.
    #
    # The kinks have to survive, though, or the curve gets cut off exactly where
    # it is interesting: where the deductible is exhausted, where the
    # coinsurance reaches its cap, at the tipping point, and at the window
    # edges.
    cap = coinsurance_cap[age_group]
    kinks = {window_from, window_to, int(expected_costs)}
    if r.tipping_point is not None:
        kinks.update({r.tipping_point - 1, r.tipping_point})
    for deductible in r.costs.columns:
        kinks.add(int(deductible))
        kinks.add(int(deductible + cap / coinsurance_rate))
    step = max(1, (window_to - window_from) // 400)
    keep = curves["Krankheitskosten"].isin(kinks) | (
        curves["Krankheitskosten"] % step == 0
    )
    curves = curves[keep]

    chart = (
        alt.Chart(curves)
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
                scale=alt.Scale(
                    domain=["kommt in Frage", "nie optimal"], range=[1.0, 0.3]
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
        .properties(height=360)
    )
    if r.tipping_point is not None:
        chart += (
            alt.Chart(pd.DataFrame({"k": [r.tipping_point]}))
            .mark_rule(strokeDash=[6, 4], color="#9aa0a6", size=2)
            .encode(x="k:Q")
        )
    here = pd.DataFrame(
        {"k": [expected_costs], "beschriftung": ["Deine erwarteten Krankheitskosten"]}
    )
    chart += alt.Chart(here).mark_rule(color="#ff4b4b", size=3).encode(x="k:Q")
    chart += (
        alt.Chart(here)
        .mark_text(
            align="left", dx=6, dy=-6, baseline="top", color="#ff4b4b",
            fontSize=12, fontWeight="bold",
        )
        .encode(x="k:Q", y=alt.value(0), text="beschriftung:N")
    )

    # Clicking the chart moves the red line. The number field stays the second
    # way in; both write the same value.
    click_point = alt.selection_point(
        name="point", fields=["Krankheitskosten"], nearest=True, on="click", empty=False
    )
    # Invisible but clickable verticals across the full height. mark_point with
    # opacity=0 does not respond to clicks; a rule with a wide stroke does.
    hit_area = (
        alt.Chart(curves[["Krankheitskosten"]].drop_duplicates())
        .mark_rule(size=8)
        .encode(x="Krankheitskosten:Q", opacity=alt.value(0))
        .add_params(click_point)
    )
    event = st.altair_chart(
        chart + hit_area, width="stretch", on_select="rerun", key=f"chart_{key}",
    )

    selected = (event.selection or {}).get("point") if event else None
    if selected:
        new_value = int(round(selected[0]["Krankheitskosten"] / 50) * 50)
        # Clamp to the range actually computed, not to its lower bound -
        # otherwise a click beyond 10,000 would jump back.
        new_value = max(0, min(cost_range, new_value))
        if new_value != expected_costs:
            # Do not set the input's key directly - it has already been
            # instantiated in this run. Note it down and apply it on the next.
            st.session_state["_clicked_costs"] = (key, new_value)
            st.rerun()

    # One caption instead of two: both explained the same picture - the vertical
    # lines and the faded curves - and two paragraphs in a row read like two
    # separate topics.
    parts = [
        f"Die **rote Linie** steht bei deinen erwarteten Krankheitskosten "
        f"({chf(expected_costs)} CHF); du kannst sie im Diagramm anklicken oder den "
        f"Betrag links eintragen. Fett gezeichnet ist die dort günstigste Franchise."
    ]
    if r.tipping_point is None:
        parts.append(
            f"Die tiefste Franchise ({r.lowest_deductible} CHF) lohnt sich im "
            f"gezeigten Bereich nie."
        )
    else:
        parts.append(
            f"Die **grau gestrichelte Linie** ist der Kipppunkt: Ab "
            f"**{chf(r.tipping_point)} CHF** lohnt sich die Franchise "
            f"{r.lowest_deductible} CHF, darunter die Franchise "
            f"{r.segments.iloc[0]['Franchise']} CHF. Zwischen bester und schlechtester "
            f"Franchise liegen bis zu **{chf(r.max_spread)} CHF pro Jahr**."
        )
        if expected_costs > r.tipping_point:
            parts.append(
                "Oberhalb des Kipppunkts ändert sich die Empfehlung nicht mehr – "
                "egal wie hoch die Kosten steigen."
            )
    if r.never_optimal:
        winners = sorted(set(r.optimal))
        parts.append(
            f"Nur die Franchisen "
            f"**{' und '.join(f'{w} CHF' for w in winners)}** sind hier je die "
            f"günstigste Wahl; die blass gezeichneten Stufen "
            f"{', '.join(str(d) for d in r.never_optimal)} CHF sind bei *keinen* "
            f"Krankheitskosten optimal."
        )
    else:
        parts.append(
            "In diesen Daten ist jede Franchisenstufe irgendwo die günstigste – "
            "sonst gewinnen nur die höchste und die tiefste."
        )
    st.caption(" ".join(parts))

    # ------------------------------- Deductibles compared at the given costs
    st.subheader("Kosten pro Franchise")
    comparison = (
        at_expected.rename("Kosten/Jahr")
        .reset_index()
        .rename(columns={"index": "Franchise"})
        .sort_values("Kosten/Jahr")
        .reset_index(drop=True)
    )
    comparison["Franchise"] = comparison["Franchise"].astype(int)
    comparison["Kosten/Jahr"] = comparison["Kosten/Jahr"].round(0)
    comparison = with_gap_to_cheapest(comparison, "Kosten/Jahr", "Mehrkosten/Jahr")
    comparison["Kosten/Monat"] = (comparison["Kosten/Jahr"] / 12).round(2)
    comparison = with_gap_to_cheapest(comparison, "Kosten/Monat", "Mehrkosten/Monat")
    st.dataframe(
        comparison,
        hide_index=True,
        width="stretch",
        column_config={
            "Franchise": st.column_config.NumberColumn(format="%d", width="small"),
            "Kosten/Jahr": st.column_config.NumberColumn(format="%.0f", width="small"),
            "Mehrkosten/Jahr": st.column_config.NumberColumn(
                format="%.0f", width="small"
            ),
            "Kosten/Monat": st.column_config.NumberColumn(format="%.2f", width="small"),
            "Mehrkosten/Monat": st.column_config.NumberColumn(
                format="%.2f", width="small"
            ),
        },
    )

    group_data = data[data["Zielgruppe"] == age_group]

    # ----------------------- The best offers for the deductible that applies
    st.subheader(f"Die günstigsten Angebote für Franchise {best_deductible} CHF")
    st.caption(
        f"Das ist die Franchise, die bei {chf(expected_costs)} CHF Krankheitskosten "
        f"am günstigsten kommt. Sortiert nach Prämie, die sieben günstigsten."
    )
    # The full ranking for this deductible - seven are shown, but today's
    # contract should appear even when it sits further down. Otherwise you only
    # see what is on offer, never where you stand.
    ranking = (
        group_data[group_data["Franchise"] == best_deductible]
        .sort_values("Prämie")
        .reset_index(drop=True)
    )
    ranking["Rang"] = ranking.index + 1

    current_row, current_rank, hit = None, None, None
    if current:
        hit = ranking[
            (ranking["Versicherername"] == current[0])
            & (ranking["Tarifbezeichnung"] == current[1])
        ]
        if not hit.empty:
            current_row = hit.iloc[0]
            current_rank = int(current_row["Rang"])

    shown = ranking.head(7)
    if current_rank is not None and current_rank > 7:
        shown = pd.concat([shown, hit], ignore_index=True)

    offers = shown[
        ["Rang", "Versicherername", "Tarifbezeichnung", "Tariftyp", "Prämie"]
    ].reset_index(drop=True)
    if offers.empty:
        st.info("Für diese Franchise gibt es keine Angebote.")
    else:
        offers = offers.rename(
            columns={
                "Versicherername": "Versicherer",
                "Tarifbezeichnung": "Tarif",
                "Tariftyp": "Typ",
            }
        )
        offers["Prämie/Jahr"] = (offers["Prämie"] * 12).round(0)
        offers = with_gap_to_cheapest(offers, "Prämie/Jahr", "Mehrkosten/Jahr")
        offers["Prämie/Monat"] = offers["Prämie"].round(2)
        offers["Typ"] = offers["Typ"].map(TARIFF_TYPES_SHORT)
        columns = ["Rang", "Versicherer", "Tarif", "Typ", "Prämie/Jahr",
                   "Mehrkosten/Jahr", "Prämie/Monat"]
        # Only create the marker column when there is something to mark -
        # otherwise an empty column sits there asking what it is missing.
        marker = [
            "◀ jetziger Versicherer"
            if current and i == current[0] and t == current[1]
            else ""
            for i, t in zip(shown["Versicherername"], shown["Tarifbezeichnung"])
        ]
        if any(marker):
            offers[""] = marker
            columns.append("")
        offers = offers[columns]

        st.dataframe(
            offers,
            hide_index=True,
            width="stretch",
            column_config={
                "Rang": st.column_config.NumberColumn(format="%d", width="small"),
                "Versicherer": st.column_config.TextColumn(width="medium"),
                "Tarif": st.column_config.TextColumn(width="small"),
                "Typ": st.column_config.TextColumn(width="small"),
                "Prämie/Jahr": st.column_config.NumberColumn(
                    format="%.0f", width="small"
                ),
                "Mehrkosten/Jahr": st.column_config.NumberColumn(
                    format="%.0f", width="small"
                ),
                "Prämie/Monat": st.column_config.NumberColumn(
                    format="%.2f", width="small"
                ),
                "": st.column_config.TextColumn(width="medium"),
            },
        )

        if current and current_rank is None:
            st.caption(
                f"**{current[0]} – {current[1]}** führt für die Franchise "
                f"{best_deductible} CHF kein Angebot, das zu den gewählten "
                f"Tarifmodellen passt."
            )
        elif current_rank == 1:
            st.success(
                f"Du hast auch {premium_year} den günstigsten Anbieter für dieses "
                f"Szenario: **{current[0]} – {current[1]}**. Ein Wechsel würde nichts "
                f"sparen."
            )
        elif current_rank is not None:
            extra = (
                float(current_row["Prämie"]) - float(ranking.iloc[0]["Prämie"])
            ) * 12
            st.info(
                f"Dein heutiger Vertrag **{current[0]} – {current[1]}** liegt auf Rang "
                f"{current_rank} von {len(ranking)}. Der günstigste Anbieter für "
                f"dieses Szenario kostet **{chf(extra)} CHF pro Jahr weniger**."
            )

        free_choice = group_data[
            (group_data["Tariftyp"] == "BASE")
            & (group_data["Franchise"] == best_deductible)
        ]
        # offers carries the short form in the column "Typ"; group_data still
        # holds the raw value in "Tariftyp".
        if not free_choice.empty and offers["Typ"].iloc[0] != TARIFF_TYPES_SHORT["BASE"]:
            cheapest_monthly = float(offers["Prämie/Monat"].iloc[0])
            free_monthly = float(free_choice["Prämie"].min())
            # Only the number gets the Swiss thousands separator - a replace on
            # the whole sentence would also swap out the commas in the text.
            surcharge_year = chf((free_monthly - cheapest_monthly) * 12)
            st.caption(
                f"Das günstigste Angebot ist ein Modell mit **eingeschränkter "
                f"Arztwahl**. Das günstigste Standardmodell mit freier Arztwahl kostet "
                f"**{surcharge_year} CHF pro Jahr mehr** ({free_monthly:.2f} statt "
                f"{cheapest_monthly:.2f} CHF im Monat). Ob die Einschränkung das wert "
                f"ist, bewertet dieses Werkzeug nicht."
            )

    st.download_button(
        "Kostenmatrix als CSV",
        r.costs.to_csv().encode("utf-8"),
        file_name=f"kostenmatrix_{age_group.lower()}_{canton}.csv",
        mime="text/csv",
        key=f"csv_{key}",
    )

    best_offer = offers.iloc[0] if not offers.empty else None
    return {
        "age_group": age_group,
        "deductible": best_deductible,
        "annual_costs": float(at_expected.min()),
        "insurer": best_offer["Versicherer"] if best_offer is not None else "—",
        "tariff": best_offer["Tarif"] if best_offer is not None else "—",
        "annual_premium": (
            float(best_offer["Prämie/Jahr"]) if best_offer is not None else 0.0
        ),
    }


def insurers_and_models(
    raw, canton: str, region: str, age_group: str, accident: str
) -> dict[str, list[str]]:
    """Insurers at this location and their tariff names, for the dropdowns."""
    data = get_data(
        raw, canton=canton, region=region, age_groups=(age_group,),
        accident_cover={age_group: accident},
        child_subgroups=tuple(CHILD_SUBGROUPS),
    )
    if data.empty:
        return {}
    grouped = (
        data.groupby("Versicherername")["Tarifbezeichnung"]
        .apply(lambda s: sorted(s.unique()))
        .to_dict()
    )
    return dict(sorted(grouped.items()))


def person_form(person: dict, person_count: int, raw) -> dict | None:
    """Every detail of one person. Returns the updated entry.

    Location and tariff models sit here rather than in a shared sidebar: a
    household can be spread across municipal boundaries, and someone who wants
    free choice of doctor for themselves does not necessarily want it for
    everyone else.
    """
    person_id = person["id"]
    top = st.columns([3, 2, 3, 3])

    location = choose_location(person_id, top[0])

    age = top[1].number_input(
        "Alter", min_value=0, max_value=120, value=int(person["age"]), step=1,
        key=f"age_{person_id}",
    )
    age_group = age_group_for_age(int(age))

    accident = top[2].radio(
        "Unfalldeckung",
        ["MIT-UNF", "OHN-UNF"],
        index=1 if age_group == ADULTS else 0,
        format_func=lambda a: "mit" if a == "MIT-UNF" else "ohne",
        horizontal=True,
        key=f"accident_{person_id}",
        help="Wer mindestens acht Stunden pro Woche bei demselben Arbeitgeber "
        "arbeitet, ist dort gegen Unfall versichert.",
    )

    costs_key = f"costs_{person_id}"
    st.session_state.setdefault(costs_key, int(person["costs"]))
    costs = top[3].number_input(
        "Erwartete Krankheitskosten pro Jahr (CHF)",
        min_value=0, step=100, key=costs_key,
        help="Der wichtigste Wert neben dem Alter. Arztbesuche, Medikamente, "
        "Therapien – alles, was über die Grundversicherung läuft.",
    )

    tariff_types = st.multiselect(
        "Tarifmodelle",
        list(TARIFF_TYPES),
        default=list(TARIFF_TYPES),
        format_func=lambda m: TARIFF_TYPES[m],
        key=f"models_{person_id}",
        help="Das Standardmodell lässt die Arztwahl frei; die übrigen schränken sie "
        "ein und sind dafür günstiger.",
    )

    # Today's contract - so the evaluation can say whether switching is worth it
    # at all, instead of only showing the theoretically cheapest.
    current_insurer, current_model = None, None
    if location is not None:
        available = insurers_and_models(
            raw, location[0], location[1], age_group, accident
        )
        if available:
            today = st.columns(2)
            current_insurer = today[0].selectbox(
                "Jetziger Versicherer",
                [None, *available],
                format_func=lambda v: "– noch keiner / unbekannt –" if v is None else v,
                key=f"current_insurer_{person_id}",
                help="Optional. Damit zeigt die Tabelle unten, auf welchem Rang dein "
                "heutiger Vertrag liegt.",
            )
            if current_insurer:
                models = available[current_insurer]
                current_model = today[1].selectbox(
                    "Jetziges Modell", models, key=f"current_model_{person_id}"
                )

    if location is None:
        st.warning(
            "Ohne gültige Postleitzahl lässt sich für diese Person nichts rechnen."
        )

    # The delete button used to sit in the same row as the tariff models, right
    # next to their own delete and expand icons - a misclick there removes the
    # whole person without asking. It now stands on its own, bottom right.
    if person_count > 1:
        _, bottom_right = st.columns([5, 1])
        if bottom_right.button("Person entfernen", key=f"remove_{person_id}"):
            st.session_state["people"] = [
                p for p in st.session_state["people"] if p["id"] != person_id
            ]
            st.rerun()

    return {
        "id": person_id,
        "age": int(age),
        "accident": accident,
        "costs": int(costs),
        "location": location,
        "tariff_types": tariff_types,
        "age_group": age_group,
        "current": (current_insurer, current_model) if current_insurer else None,
    }
