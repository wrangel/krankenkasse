"""Interface language.

One JSON file per language under locales/, flat dotted keys, loaded once and
cached. `t("key", name=value)` looks the key up in the chosen language and
formats it.

Three decisions worth knowing:

* **German is the fallback, not English.** It is the language this was written
  in and the only one checked line by line against the law and the BAG's
  wording. A key missing from another file falls back to German rather than
  disappearing, so a gap shows up as untranslated text instead of a blank.
* **Only the interface is translated.** Insurer names and tariff names come
  from the BAG file in German and stay that way - a French page will still say
  "Sanitas Grundversicherungen AG - TelMed Basic". There is nothing to
  translate them from.
* **Table headers are translated, CSV column names are not.** On screen a
  French reader should not meet "Mehrkosten/Monat"; in an exported file the
  column names must stay put, or the same export is incomparable between two
  people who happened to use different languages. The DataFrames therefore
  keep German column names and the translation happens in column_config.

Romansh is deliberately absent. The BAG publishes no Romansh source text, the
written standard is contested (Rumantsch Grischun against the five idioms), and
a visibly machine-translated page about somebody's money and health would serve
Romansh speakers worse than the German one they can already read.
"""

import json
import re
from functools import lru_cache

import streamlit as st

from constants import PROJECT_DIR

LOCALES_DIR = PROJECT_DIR / "locales"
FALLBACK = "de"

# The order they appear in the picker. Endonyms, because a French speaker looks
# for "Français", not for "Französisch".
LANGUAGES = {
    "de": "Deutsch",
    "fr": "Français",
    "it": "Italiano",
    "en": "English",
}

_LANG_KEY = "ui_language"


@lru_cache(maxsize=None)
def _catalogue(language: str) -> dict[str, str]:
    path = LOCALES_DIR / f"{language}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def current_language() -> str:
    return st.session_state.get(_LANG_KEY, FALLBACK)


def set_language(language: str) -> None:
    st.session_state[_LANG_KEY] = language if language in LANGUAGES else FALLBACK


def t(key: str, **kwargs) -> str:
    """The string for `key` in the chosen language, formatted with kwargs."""
    language = current_language()
    text = _catalogue(language).get(key)
    if text is None:
        text = _catalogue(FALLBACK).get(key)
    if text is None:
        # Visible on the page rather than silent, so a missing key is found
        # during a glance at the app instead of by a user.
        return f"⟦{key}⟧"
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        # A placeholder that a translation got wrong must not take the page
        # down; show the untranslated German, which is known to be correct.
        fallback = _catalogue(FALLBACK).get(key, text)
        try:
            return fallback.format(**kwargs)
        except Exception:
            return fallback


def per_language_key(key: str, default=None) -> str:
    """A widget key that changes with the language, carrying the value along.

    A selectbox or multiselect keeps showing the labels its value had when it
    was chosen: switching language reruns format_func, but the chips and the
    selected entry stay in the old language while the label around them
    changes. A key per language gives a fresh widget instead.

    The value itself lives language-neutrally under `key` - the caller writes
    it back after the widget - and that is also what persistence stores. Keys
    for the other languages are dropped, so switching back reseeds from the
    current value rather than reviving an old one.
    """
    widget_key = f"{key}@{current_language()}"
    if widget_key not in st.session_state:
        for language in LANGUAGES:
            st.session_state.pop(f"{key}@{language}", None)
        st.session_state[widget_key] = st.session_state.get(key, default)
    return widget_key


def language_picker(container=None) -> None:
    """The language switch, at the very top.

    Rendered into `container` so the caller can place it beside the wordmark
    rather than above it - stacked at the top of the page it read as the first
    thing on the site, which is not what it is.

    Only the languages you are *not* reading are offered. Showing all four with
    one of them marked is a form control; showing the three alternatives is a
    choice, and it needs no label, no radio and no explanation - which language
    you are in is evident from the page itself.
    """
    others = [c for c in LANGUAGES if c != current_language()]
    target = container if container is not None else st
    for code in others:
        if target.button(LANGUAGES[code], key=f"lang_{code}", width="stretch"):
            set_language(code)
            st.rerun()


_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")


def t_html(key: str, **kwargs) -> str:
    """t(), rendered as HTML for use inside a raw HTML block.

    Streamlit renders markdown, and it renders raw HTML, but it does not render
    markdown *inside* raw HTML - the links in the footer came out as literal
    [text](url). Translating the few markdown constructs the catalogues use
    keeps the catalogues readable for whoever translates them: they write
    [Quellcode](url), not an anchor tag.
    """
    text = t(key, **kwargs)
    text = _LINK.sub(r'<a href="\2">\1</a>', text)
    return _BOLD.sub(r"<strong>\1</strong>", text)
