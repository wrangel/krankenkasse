"""Grundversicherung: die günstigste Lösung für deine Situation - entry point.

Only the sequence lives here: set up the page, load the data, collect the
people, show each person's report, and the household total at the end. The
computation is in calculation.py, the drawing in the view_* modules.
"""

from datetime import date

import streamlit as st
import streamlit.components.v1 as components

from calculation import available_tariff_types, children_with_one_insurer, get_data
from common import age_group_for_age, premiums
from i18n import language_picker, t
from constants import (
    ADULTS,
    CHILD_SUBGROUPS,
    CHILDREN,
    COFFEE_URL,
    CONTACT_EMAIL,
    DEFAULT_PERSON,
    OPENDATA_URL,
    PRIMINFO_URL,
    REPO_URL,
    coinsurance_cap,
    coinsurance_rate,
    environmental_rebate_default,
)
from persistence import handle_forget, request_forget, restore, save
from theme import apply_person_colours, colour_for_person, configure_page
from view_household import household_total
from view_person import person_form, person_summary, person_view

configure_page()

# The picker comes before anything else that produces text, so the very first
# thing drawn is already in the chosen language.
language_picker()

raw = premiums(7)

# Put back what this browser had last time, before a single widget is drawn -
# otherwise the form renders with defaults and then visibly rewrites itself.
# The browser answers on the run after this one, so the first pass stops here.
forgetting = handle_forget()

if not restore(available_tariff_types(raw)):
    st.spinner(t("loading.moment"))
    st.stop()

st.session_state.setdefault("people", [dict(DEFAULT_PERSON)])

st.title(t("title"))
st.caption(t("lead"))

# What "Gesamtkosten" means, before the first one is shown. The figures come
# from the constants rather than the sentence, so the text cannot drift from
# what is actually computed.
st.caption(
    t(
        "total_costs_explainer",
        rate=f"{coinsurance_rate:.0%}",
        cap_adult=coinsurance_cap[ADULTS],
        cap_child=coinsurance_cap[CHILDREN],
    )
)
st.info(
    t(
        "data_banner",
        year=int(raw["Geschäftsjahr"].max()),
        rebate_year=f"{environmental_rebate_default * 12:.2f}",
        rebate_month=f"{environmental_rebate_default:.2f}",
    ),
    icon="ℹ️",
)

people = st.session_state["people"]


# How many children live in the household has to be settled before the first
# person is drawn - which tariff tiers are open to a child depends on it. The
# ages are already in session_state, because Streamlit holds each input's value
# under its key; for a person just added the key does not exist yet, and then
# their starting value applies.
def _age_of(entry: dict) -> int:
    return int(st.session_state.get(f"age_{entry['id']}", entry["age"]))


child_ids = [p["id"] for p in people if age_group_for_age(_age_of(p)) == CHILDREN]

apply_person_colours(len(people))

updated = []
results = []
for number, person in enumerate(people, start=1):
    with st.container(border=True, key=f"person_box_{number}"):
        head = st.columns([6, 2])
        head[0].markdown(
            f"<span style='color:{colour_for_person(number)}'>●</span> "
            f"**{t('person.heading', n=number)}**",
            unsafe_allow_html=True,
        )

        # A named button rather than just an arrow: it says what it does, and it
        # always sits in the same place - whether the report is open or not.
        open_key = f"open_{person['id']}"
        is_open = st.session_state.setdefault(open_key, number == 1)
        if head[1].button(
                t("person.collapse") if is_open else t("person.expand"),
            key=f"toggle_{person['id']}",
            width="stretch",
        ):
            st.session_state[open_key] = not is_open
            st.rerun()

        entry = person_form(person, len(people), raw)
        updated.append(entry)

        if entry["location"] is None:
            continue

        age_group = entry["age_group"]
        tiers = ("K1",)
        if age_group == CHILDREN and is_open and len(child_ids) > 1:
            st.caption(
                t("person.child_note",
                  i=child_ids.index(person["id"]) + 1, n=len(child_ids))
            )

        if is_open:
            st.markdown("---")
            result = person_view(
                raw, entry["location"][0], entry["location"][1], age_group,
                {age_group: entry["accident"]}, entry["tariff_types"], tiers,
                environmental_rebate_default, entry["costs"], person["id"],
                entry["current"],
            )
        else:
            result = person_summary(
                raw, entry["location"][0], entry["location"][1], age_group,
                {age_group: entry["accident"]}, entry["tariff_types"], tiers,
                environmental_rebate_default, entry["costs"],
            )
        if result:
            result["town"] = entry["location"][2].split(" (")[0]
            result["id"] = person["id"]
            result["costs"] = entry["costs"]
            result["location"] = entry["location"]
            result["accident"] = entry["accident"]
            result["tariff_types"] = entry["tariff_types"]
            results.append(result)

st.session_state["people"] = [
    {k: v for k, v in p.items() if k in {"id", "age", "accident", "costs"}}
    for p in updated
]

if not forgetting:
    save(available_tariff_types(raw))

if st.button(t("add_person"), key="add_person", width="stretch"):
    next_id = max((p["id"] for p in updated), default=0) + 1
    st.session_state["people"] = st.session_state["people"] + [
        {"id": next_id, "age": 8, "accident": "MIT-UNF", "costs": 500}
    ]
    # Expand the new person, collapse the rest - otherwise you face a page full
    # of open reports and cannot see what was just added.
    for p in updated:
        st.session_state[f"open_{p['id']}"] = False
    st.session_state[f"open_{next_id}"] = True
    st.session_state["_scroll_to"] = next_id
    st.rerun()

# Jump to the person just added. Streamlit keeps the scroll position across
# reruns; without this you land in the middle of the previous person's report
# and never see the new input fields.
scroll_target = st.session_state.pop("_scroll_to", None)
if scroll_target is not None:
    target_number = next(
        (i for i, p in enumerate(updated, start=1) if p["id"] == scroll_target), None
    )
    if target_number:
        # What scrolls is the main area section[data-testid="stMain"], not the
        # window - scrollIntoView grabs the wrong container and has no effect.
        # Several attempts, because Streamlit restores the previous position
        # only after drawing and would immediately overwrite an instant jump.
        components.html(
            f"""
            <script>
              const doc = window.parent.document;
              let attempts = 0;
              const jump = () => {{
                const area = doc.querySelector('section[data-testid="stMain"]');
                const box = doc.querySelector('.st-key-person_box_{target_number}');
                if (area && box) {{
                  const target = box.getBoundingClientRect().top
                               - area.getBoundingClientRect().top
                               + area.scrollTop - 16;
                  area.scrollTo({{top: target, behavior: 'smooth'}});
                }}
                if (++attempts < 8) setTimeout(jump, 200);
              }};
              setTimeout(jump, 120);
            </script>
            """,
            height=0,
        )

# Sibling discount: only available when all children are with the same insurer.
# It is therefore computed for the children jointly and set against free choice
# without a discount - the decision belongs to the household, not to the
# individual child.
shared = None
child_results = [r for r in results if r["age_group"] == CHILDREN]
if len(child_results) >= 2:
    first = child_results[0]
    child_data = get_data(
        raw,
        canton=first["location"][0],
        region=first["location"][1],
        age_groups=(CHILDREN,),
        accident_cover={CHILDREN: first["accident"]},
        child_subgroups=tuple(CHILD_SUBGROUPS),
        tariff_types=tuple(first["tariff_types"]) if first["tariff_types"] else None,
    )
    shared = children_with_one_insurer(
        child_data,
        [float(r["costs"]) for r in child_results],
        environmental_rebate_default,
    )

household_total(results, len(child_ids), shared)

st.markdown("---")

# The same limitations as in the README - whoever uses the app does not read the
# README. Collapsed, so the page does not end in small print, but reachable from
# anywhere on the page.
with st.expander(t("disclaimer.title")):
    st.markdown(t("disclaimer.body", priminfo=PRIMINFO_URL))

left, right = st.columns([3, 1])
left.caption(t("reload_data.caption"))
if right.button(t("reload_data.button")):
    st.cache_data.clear()
    premiums(0)
    st.rerun()

# Anything kept on the visitor's machine needs a way to be got rid of, in plain
# sight rather than buried in browser settings.
links, clear = st.columns([3, 1])
links.caption(t("storage.caption"))
if clear.button(t("storage.forget_button"), key="forget_inputs_button", width="stretch"):
    request_forget()
    st.rerun()

st.markdown("---")

# The footnote for the asterisk on "Kipppunkt" in each person's chart caption.
# It sits here once rather than under every chart - with four people in the
# household the same paragraph would otherwise appear four times.
st.caption(t("footnote.tipping_point"))

# The PHARM category. Worth stating plainly: the vocabulary and the data
# disagree, and the app quietly departs from what priminfo offers, so it should
# say why rather than leave someone wondering where Apothekenmodelle went.
st.caption(t("footnote.pharm", year=int(raw["Geschäftsjahr"].max())))

# Why the thing exists. It belongs next to the contact line: someone who writes
# in should know who they are writing to and what question the tool grew out of.
st.caption(t("motivation"))

# Contact and provenance. The address is an alias, not the real mailbox - see
# CONTACT_EMAIL in constants.py. Saying what the reply is *not* keeps the
# expectation straight: this is a calculation tool, and an individual answer
# about somebody's own policy would be the advice the page disclaims.
# Kept to one quiet line, and placed after the explanation of why the app
# exists rather than before it: the ask reads very differently once someone
# knows it was built for one family and given away.
st.caption(t("footer.coffee", url=COFFEE_URL))

st.caption(t("footer.contact", mailto=f"mailto:{CONTACT_EMAIL}"))
st.caption(
    t("footer.provenance", repo=REPO_URL, opendata=OPENDATA_URL,
      priminfo=PRIMINFO_URL)
)
st.caption(
    t("footer.copyright", year=date.today().year,
      license=f"{REPO_URL}/blob/main/LICENSE")
)
