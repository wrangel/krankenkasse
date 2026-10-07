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


def language_picker() -> None:
    """The selector, at the very top of the page."""
    codes = list(LANGUAGES)
    current = current_language()
    chosen = st.radio(
        # Collapsed, so this is only read by screen readers - which is exactly
        # why it must not be German-only. All four at once needs no key and is
        # right whatever the page is currently set to.
        "Sprache / Langue / Lingua / Language",
        codes,
        index=codes.index(current) if current in codes else 0,
        format_func=lambda c: LANGUAGES[c],
        horizontal=True,
        key="language_picker",
        label_visibility="collapsed",
    )
    if chosen != current:
        set_language(chosen)
        st.rerun()
