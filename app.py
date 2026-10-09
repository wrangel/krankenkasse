"""Grundversicherung: die günstigste Lösung für deine Situation - entry point.

Only the sequence lives here: set up the page, load the data, collect the
people, show each person's report, and the household total at the end. The
computation is in calculation.py, the drawing in the view_* modules.
"""

import html
import sys
from datetime import date

import streamlit as st
import streamlit.components.v1 as components

from calculation import available_tariff_types, children_with_one_insurer, get_data
from common import age_group_for_age, premiums
from i18n import language_picker, t, t_html
from constants import (
    ADULTS,
    CHILD_SUBGROUPS,
    CHILDREN,
    COFFEE_URL,
    CONTACT_EMAIL,
    GITHUB_PROFILE_URL,
    OTHER_APPS_URL,
    DEFAULT_PERSON,
    FORMULA_URL,
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


# A visitor must not be shown a traceback with our file paths in it. The BAG
# can be unreachable for reasons that are nobody's fault - and on the NAS it
# was, when the container could route out but not resolve names. urllib's
# URLError is an OSError, so this catches the network failures without
# swallowing genuine bugs.
try:
    raw = premiums(7)
except OSError as problem:
    # The visitor gets a sentence; the log gets the cause. Without this the
    # friendly message hides exactly the detail needed to fix the outage - and
    # it did, for one round of debugging.
    print(
        f"BAG download failed: {type(problem).__name__}: {problem}",
        file=sys.stderr,
        flush=True,
    )
    st.error(t("error.data_unavailable"))
    st.stop()

# Put back what this browser had last time, before a single widget is drawn -
# otherwise the form renders with defaults and then visibly rewrites itself.
# The browser answers on the run after this one, so the first pass stops here.
forgetting = handle_forget()

if not restore(available_tariff_types(raw)):
    st.spinner(t("loading.moment"))
    st.stop()

# The tab title was set above, before restore() knew the stored language - so a
# returning English visitor got the German title. Set again, now it is known.
st.set_page_config(page_title=t("page_title"))

st.session_state.setdefault("people", [dict(DEFAULT_PERSON)])

# Wordmark and language switch on one row, the switch subordinate on the right.
# Stacked above the title it read as the first thing on the site, which it is
# not. The wordmark is markup rather than st.title so the two halves of the name
# can be coloured - "via" plain, "prima" in the accent - which gives it presence
# without needing a logo.
head_left, head_right = st.columns([5, 1], vertical_alignment="center")
head_left.markdown(
    '<h1 class="wordmark">via<span class="accent">prima</span></h1>', unsafe_allow_html=True
)
language_picker(head_right)
premium_year = int(raw["Geschäftsjahr"].max())
# Two lines, one heading. A markdown heading ends at the line break - the second
# line would drop out as body text - so both go into a single <h3>.
subtitle_lines = t("subtitle", year=premium_year).split("\n")
st.markdown(
    '<h3 class="subtitle">'
    + "<br>".join(html.escape(line.strip()) for line in subtitle_lines)
    + "</h3>",
    unsafe_allow_html=True,
)
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
# What the app is and is not, and nothing else. The data source and the
# environmental levy moved to footnote *, the premium year into the subtitle.
st.info(t("data_banner"), icon="ℹ️")

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
                environmental_rebate_default, entry["costs"], entry["current"],
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

# The two housekeeping rows share one shape: caption left, a button filling the
# same right-hand column, so the buttons line up as a pair.
left, right = st.columns([3, 1], vertical_alignment="center")
left.caption(t("reload_data.caption"))
if right.button(t("reload_data.button"), width="stretch"):
    st.cache_data.clear()
    premiums(0)
    st.rerun()

# Anything kept on the visitor's machine needs a way to be got rid of, in plain
# sight rather than buried in browser settings.
links, clear = st.columns([3, 1], vertical_alignment="center")
links.caption(t("storage.caption"))
if clear.button(t("storage.forget_button"), key="forget_inputs_button", width="stretch"):
    request_forget()
    st.rerun()

st.markdown("---")

# The footnotes, in the order their markers appear: * on the data source in the
# lead, ** on the Kipppunkt in each chart caption, *** on the tariff-model help.
# Written once here rather than beside each marker - with four people in the
# household the Kipppunkt note would otherwise repeat four times.
st.caption(
    t("footnote.data", opendata=OPENDATA_URL,
      rebate_year=f"{environmental_rebate_default * 12:.2f}")
)
st.caption(t("footnote.tipping_point", formula=FORMULA_URL))
st.caption(t("footnote.pharm", year=premium_year))

st.markdown("---")

# Why the thing exists, then the two asks. Someone who writes in should know who
# they are writing to and what question the tool grew out of; the coffee reads
# very differently once they know it was built for one family and given away.
st.caption(t("motivation"))
st.caption(t("footer.coffee", url=COFFEE_URL))
st.caption(t("footer.contact", mailto=f"mailto:{CONTACT_EMAIL}"))

# The footer block from abstractaltitudes, same rows in the same order: what you
# can do, what it is built on, what else I have made, the copyright. Each row is
# separate links spaced by a gap, no separator characters, as there. The
# paragraphs above stay at reading size because here they carry the footnotes;
# only this block recedes.


def footer_row(links, label=None):
    """One centred row of footer links; `label` is a dimmer leading word."""
    items = [f'<span class="brand-footer-label">{html.escape(label)}</span>'] if label else []
    for text, url in links:
        external = "" if url.startswith("mailto:") else ' target="_blank" rel="noopener noreferrer"'
        items.append(f'<a href="{html.escape(url)}"{external}>{html.escape(text)}</a>')
    return f'<div class="brand-footer-row">{"".join(items)}</div>'


st.markdown(
    '<div class="brand-footer">'
    + footer_row([
        (t("footer.link.contact"), f"mailto:{CONTACT_EMAIL}"),
        (t("footer.link.source"), REPO_URL),
        (t("footer.link.license"), f"{REPO_URL}/blob/main/LICENSE"),
        (t("footer.link.coffee"), COFFEE_URL),
    ])
    + footer_row([
        ("wrangel", GITHUB_PROFILE_URL),
        ("opendata.swiss", OPENDATA_URL),
        ("priminfo.admin.ch", PRIMINFO_URL),
        ("Streamlit", "https://streamlit.io"),
    ])
    + footer_row([("Abstract Altitudes", OTHER_APPS_URL)], label=t("footer.also_by_me"))
    + '<p class="brand-footer-copyright">'
    + html.escape(t("footer.copyright", year=date.today().year))
    + "</p></div>",
    unsafe_allow_html=True,
)
