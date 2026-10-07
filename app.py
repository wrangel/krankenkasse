"""Grundversicherung: die günstigste Prämie finden - entry point.

Only the sequence lives here: set up the page, load the data, collect the
people, show each person's report, and the household total at the end. The
computation is in calculation.py, the drawing in the view_* modules.
"""

from datetime import date

import streamlit as st
import streamlit.components.v1 as components

from common import age_group_for_age, premiums
from constants import (
    ADULTS,
    CHILD_SUBGROUPS,
    CHILDREN,
    CONTACT_EMAIL,
    OPENDATA_URL,
    PRIMINFO_URL,
    REPO_URL,
    coinsurance_cap,
    coinsurance_rate,
    environmental_rebate_default,
)
from theme import apply_person_colours, colour_for_person, configure_page
from calculation import children_with_one_insurer, get_data
from view_household import household_total
from view_person import person_form, person_summary, person_view

configure_page()

st.session_state.setdefault(
    "people", [{"id": 1, "age": 40, "accident": "OHN-UNF", "costs": 1000}]
)

raw = premiums(7)

st.title("Grundversicherung: die günstigste Prämie finden")
st.caption(
    "**Du sagst, was du im Jahr an Arztkosten erwartest. Die App rechnet den Rest** – "
    "Versicherer, Modell und Franchise mit den tiefsten Gesamtkosten, für jede Person "
    "im Haushalt und beschränkt auf die Tarifmodelle, die für dich in Frage kommen. "
    "Gerechnet wird aus den amtlichen Prämiendaten der **Grundversicherung**."
)

# What "Gesamtkosten" means, before the first one is shown. The figures come
# from the constants rather than the sentence, so the text cannot drift from
# what is actually computed.
st.caption(
    f"**Gesamtkosten sind Prämien + Franchise + Selbstbehalt** – alles, was du "
    f"im Jahr für die Grundversicherung selber bezahlst. Die Prämie allein ist die "
    f"falsche Grösse, denn die tiefste Prämie hat immer die höchste Franchise; "
    f"ob sich das lohnt, hängt an deinen Krankheitskosten. Der Selbstbehalt "
    f"beträgt {coinsurance_rate:.0%} der Kosten oberhalb der Franchise, aber "
    f"höchstens **{coinsurance_cap[ADULTS]} CHF pro Jahr** "
    f"({coinsurance_cap[CHILDREN]} CHF bei Kindern) – darüber zahlt die "
    f"Krankenkasse alles."
)
st.info(
    f"**Prämienjahr {int(raw['Geschäftsjahr'].max())}** · Datenquelle: BAG-Prämiendaten "
    f"über opendata.swiss · Rückerstattung Umweltabgaben "
    f"**{environmental_rebate_default * 12:.2f} CHF pro Jahr** "
    f"({environmental_rebate_default:.2f} pro Monat), für alle Versicherten gleich und "
    f"bereits von den Prämien abgezogen.\n\n"
    f"**Rechenhilfe, keine Finanz- oder Versicherungsberatung.** Was nicht "
    f"berücksichtigt ist, steht unten auf der Seite.",
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
            f"**{number}. Person**",
            unsafe_allow_html=True,
        )

        # A named button rather than just an arrow: it says what it does, and it
        # always sits in the same place - whether the report is open or not.
        open_key = f"open_{person['id']}"
        is_open = st.session_state.setdefault(open_key, number == 1)
        if head[1].button(
            "Einklappen" if is_open else "Ausklappen",
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
                f"Kind {child_ids.index(person['id']) + 1} von {len(child_ids)}. "
                f"Unten steht dieses Kind einzeln gerechnet, zum Normaltarif K1. "
                f"Geschwisterrabatte gibt es nur, wenn **alle** Kinder beim "
                f"gleichen Versicherer sind – dazu der eigene Abschnitt weiter "
                f"unten."
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

if st.button("➕ Weitere Person hinzufügen", key="add_person", width="stretch"):
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
with st.expander("Was diese Rechnung nicht berücksichtigt"):
    st.markdown(
        """
Diese Anwendung ist eine **Rechenhilfe und keine Finanz- oder
Versicherungsberatung**. Sie rechnet aus den amtlichen Prämiendaten, was die
angegebene Person bei den angegebenen Krankheitskosten zahlen würde – mehr nicht.
Welche Versicherung zu jemandem passt, hängt an Dingen, die hier nicht vorkommen:

- **Prämienverbilligung**, Zusatzversicherungen, der Spitalbeitrag von 15 CHF pro
  Tag sowie Besonderheiten einzelner Modelle.
- **Einschränkungen bei der Arztwahl.** Die alternativen Modelle sind in den
  Prämien enthalten, ihre Auflagen aber nicht bewertet. Das günstigste Angebot ist
  nicht automatisch das passendste – die günstigsten sind fast immer Modelle, die
  die Arztwahl einschränken.
- **Die Familien-Höchstgrenze** der Kostenbeteiligung (Art. 93 Abs. 3 KVV) ist in
  den Summen nicht eingerechnet. Bei drei oder mehr Kindern fällt die reale
  Belastung also tiefer aus als hier gezeigt.
- **Unterschiedliche Franchisen der Kinder.** Die Verordnung überlässt die
  Höchstbeteiligung dann dem Versicherer; hier wird eine gemeinsame Franchise
  angenommen.
- **Der Kipppunkt ist auf den Franken genau, aber dort geht es um Rappen.** Welche
  Richtung er anzeigt – hohe oder tiefe Franchise – ist belastbar, der genaue
  Betrag nicht.

Massgebend sind die Angaben der Versicherer und das offizielle
[priminfo.admin.ch](https://www.priminfo.admin.ch). Für Entscheide mit Folgen
lohnt sich eine Beratung bei einer unabhängigen Stelle.
        """
    )

left, right = st.columns([3, 1])
left.caption(
    "Die Prämiendaten werden beim ersten Aufruf geladen und sieben Tage "
    "zwischengespeichert."
)
if right.button("Prämiendaten neu laden"):
    st.cache_data.clear()
    premiums(0)
    st.rerun()

st.markdown("---")

# The footnote for the asterisk on "Kipppunkt" in each person's chart caption.
# It sits here once rather than under every chart - with four people in the
# household the same paragraph would otherwise appear four times.
st.caption(
    "\\* Der Kipppunkt wird nicht aus einer Faustregel übernommen, sondern für "
    "deine Region, deine Altersklasse und die tatsächlich angebotenen Tarife "
    "gerechnet. Dass die mittleren Franchisen nie gewinnen, ist eine Beobachtung "
    "aus diesen Daten – über Jahre hinweg gemacht und unabhängig bestätigt: Eine "
    "öffentlich publizierte Kurzformel für die Stufen 300 und 2500 kommt auf den "
    "Franken genau auf dasselbe Ergebnis. Sie vergleicht allerdings nur diese "
    "beiden Stufen; die dazwischen rechnet erst diese App durch."
)

# Why the thing exists. It belongs next to the contact line: someone who writes
# in should know who they are writing to and what question the tool grew out of.
st.caption(
    "**Warum es diese App gibt.** Ich wusste, dass höhere erwartete "
    "Krankheitskosten eine tiefere Franchise sinnvoll machen, und umgekehrt, aber "
    "ich wusste nicht, bei welchen Kosten sich welche Franchise lohnt, damit das "
    "Wachstum der Gesundheitskosten für meine Familie minimiert werden konnte. "
    "Dafür habe ich diese App entwickelt."
)

# Contact and provenance. The address is an alias, not the real mailbox - see
# CONTACT_EMAIL in constants.py. Saying what the reply is *not* keeps the
# expectation straight: this is a calculation tool, and an individual answer
# about somebody's own policy would be the advice the page disclaims.
st.caption(
    f"**Fehler gefunden, Frage, Rückmeldung?** "
    f"[Schreib mir]({f'mailto:{CONTACT_EMAIL}'}) – gerne auch, wenn eine Zahl "
    f"nicht stimmt. Keine Beratung zu einzelnen Policen."
)
st.caption(
    f"[Quellcode auf GitHub]({REPO_URL}) · "
    f"Prämiendaten vom BAG über [opendata.swiss]({OPENDATA_URL}) · "
    f"amtlicher Vergleich auf [priminfo.admin.ch]({PRIMINFO_URL}) · "
    f"gebaut mit [Streamlit](https://streamlit.io)"
)
st.caption(
    f"© 2023–{date.today().year} Matthias Wettstein · "
    f"[MIT-Lizenz]({REPO_URL}/blob/main/LICENSE) · "
    f"Rechenhilfe, keine Finanz- oder Versicherungsberatung."
)
