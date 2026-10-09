"""Shared building blocks: loading data, formatting numbers, location, age class.

Everything several views need that is not a view of its own.
"""

import html
import json

import pandas as pd
import streamlit as st

from constants import ADULTS, CHILDREN, DEFAULT_POSTCODE, REGIONS_FILE, YOUNG_ADULTS
from i18n import t
from calculation import load_premiums


# The message says why it takes a moment and that it only takes it once. On the
# first call after a restart the BAG file is parsed - noticeably slow on the
# Synology - and is then held ready in parsed form.
@st.cache_data(show_spinner=False)
def _premiums(max_age_days: int):
    return load_premiums(max_age_days)


def premiums(max_age_days: int):
    # The spinner text is translated, so it cannot sit in the cache decorator,
    # which is evaluated once at import time before a language is known.
    with st.spinner(t("loading.premiums")):
        return _premiums(max_age_days)


def chf(amount: float, decimals: int = 0) -> str:
    return f"{amount:,.{decimals}f}".replace(",", "'")


def show_table(
    df: pd.DataFrame,
    numbers: dict[str, int | None],
    highlight: list[bool] | None = None,
    counters: tuple[str, ...] = (),
) -> None:
    """Draw `df` as a plain HTML table, styled by .vp-table in theme.py.

    Not st.dataframe: that draws on a canvas and either cut long insurer
    names or, stretched to the page, spread spare width over every column
    and left right-set numbers far from their left-set headers - and its
    headers cannot be right-aligned at all. Here the browser sizes the
    columns: number columns shrink to their content and sit right, header
    included; text columns take the remaining width, so the table runs flush
    with the page like everything else and no name is ever cut.

    `numbers` maps the right-aligned columns to their decimals for the Swiss
    format (1'318), or to None for a column that is already text ("nein").
    Headers are the translated col.* labels; the DataFrame keeps its German
    column names for the CSV exports. `highlight` tints rows, e.g. today's
    contract. `counters` (Rang, Nr.) stay left but as narrow as numbers.
    """

    def css(c: str) -> str:
        if c in numbers:
            return ' class="num"'
        return ' class="counter"' if c in counters else ""

    head = "".join(f"<th{css(c)}>{html.escape(t(f'col.{c}'))}</th>"
                   for c in df.columns)
    rows = []
    for i, (_, row) in enumerate(df.iterrows()):
        cells = []
        for c in df.columns:
            value = row[c]
            if not isinstance(value, str) and pd.isna(value):
                text = ""
            elif c in numbers and numbers[c] is not None:
                text = chf(float(value), numbers[c])
            else:
                text = str(value)
            cells.append(f"<td{css(c)}>{html.escape(text)}</td>")
        current = ' class="current"' if highlight and highlight[i] else ""
        rows.append(f"<tr{current}>{''.join(cells)}</tr>")
    st.markdown(
        f'<div class="vp-table-wrap"><table class="vp-table"><thead><tr>{head}'
        f'</tr></thead><tbody>{"".join(rows)}</tbody></table></div>',
        unsafe_allow_html=True,
    )


@st.cache_data
def regions_by_postcode() -> dict[str, list[dict]]:
    """Postcode -> possible canton/region combinations (refresh_regions.py)."""
    if not REGIONS_FILE.exists():
        return {}
    return json.loads(REGIONS_FILE.read_text(encoding="utf-8"))


def age_group_for_age(age: int) -> str:
    """The premium age class under the KVG.

    For premiums the KVG knows exactly three classes (Art. 61 para. 3 KVG,
    names per the BAG's "Erläuterungen zu den Prämiendaten"):

        up to 18    Kinder             (AKA_01_KIN)
        19 - 25     Junge Erwachsene   (AKA_02_JUG)
        26 and up   Erwachsene         (AKA_03_ERW)

    There is no class called "Jugendliche", and for premium purposes a
    fourteen-year-old is a child - not only up to 12. Note that the step is by
    year of birth, not by birthday (Art. 89 para. 3 KVV); this app simplifies
    and works with the age.
    """
    if age <= 18:
        return CHILDREN
    if age <= 25:
        return YOUNG_ADULTS
    return ADULTS


def choose_location(key: int, column=None) -> tuple[str, str, str] | None:
    """Ask for the postcode and look up canton and premium region.

    The premium region helps determine the premium, but hardly anyone knows
    which one they live in - everyone knows their postcode. Roughly every
    twelfth postcode does lie in more than one region or canton, though; in that
    case the town is asked for as well, rather than silently taking the first.

    Returns (canton, region, label) or None if nothing matches.
    """
    target = column if column is not None else st
    mapping = regions_by_postcode()
    if not mapping:
        target.error(t("form.regions_missing"))
        return None

    # Seed session_state once instead of passing value= alongside key=.
    # Streamlit warns when a widget is given both, and it is right to: the
    # restored entry and the default disagree, and which one wins is not
    # obvious from the call. Seeding makes session_state the single source and
    # leaves a restored postcode untouched.
    postcode_key = f"postcode_{key}"
    st.session_state.setdefault(postcode_key, DEFAULT_POSTCODE)
    postcode = target.text_input(
        t("form.postcode"), max_chars=4, key=postcode_key
    ).strip()
    entries = mapping.get(postcode)
    if not entries:
        if postcode:
            target.warning(t("form.postcode_unknown", plz=postcode))
        return None

    variants = {(e["canton"], e["region"]) for e in entries}
    if len(variants) > 1:
        chosen = target.selectbox(
            t("form.town"),
            entries,
            format_func=lambda e: f"{e['town']} ({e['canton']}, {e['region']})",
            key=f"town_{key}",
            help=t("form.town_help"),
        )
    else:
        chosen = entries[0]

    return (
        chosen["canton"],
        f"PR-REG CH{chosen['region']}",
        f"{postcode} {chosen['town']} ({chosen['canton']}, Region {chosen['region']})",
    )


def with_gap_to_cheapest(
    table: pd.DataFrame, column: str, new_column: str
) -> pd.DataFrame:
    """Insert, right next to `column`, the gap to the cheapest offer.

    The cheapest gets 0, every other one the surcharge against it. Only that
    makes it visible whether a rank is a real lead or a rounding difference.
    """
    values = table[column]
    table.insert(
        table.columns.get_loc(column) + 1,
        new_column,
        (values - values.min()).round(2),
    )
    return table
