"""Seiteneinstellungen und Aussehen.

Hier steht, was die ganze Seite betrifft: Titel, Breite und die wenigen
Stilregeln, mit denen Streamlits Voreinstellungen überschrieben werden.
"""

import streamlit as st


def seite_einrichten() -> None:
    """Einmal pro Lauf aufzurufen, vor allem anderen."""
    st.set_page_config(page_title="Grundversicherung: die günstigste Prämie finden", page_icon="🏥", layout="wide")

    # Die Auswahlchips der Mehrfachauswahl kommen in der Signalfarbe des Themes. Die
    # gehört den Knöpfen, die etwas auslösen - eine Liste gewählter Tarifmodelle ist
    # eine Angabe, keine Warnung. Deshalb neutral grau.
    st.markdown(
        """
        <style>
          [data-testid="stMultiSelectTagsContainer"] span[data-tag] {
              background-color: rgba(250, 250, 250, 0.14) !important;
              color: inherit !important;
          }
          [data-testid="stMultiSelectTagsContainer"] span[data-tag] svg {
              fill: currentColor !important;
          }
          /* Hinzufügen grün, Entfernen rot - die Farbe soll sagen, was passiert.
             Streamlit hängt den Widget-Schlüssel als Klasse st-key-… an den
             Container, das ist der einzige verlässliche Haken auf einen bestimmten
             Knopf. */
          .st-key-person_hinzu button {
              background-color: #1b7f4d !important;
              border-color: #1b7f4d !important;
              color: #ffffff !important;
          }
          .st-key-person_hinzu button:hover {
              background-color: #166b41 !important;
          }
          [class*="st-key-weg_"] button {
              background-color: transparent !important;
              border-color: #c2341f !important;
              color: #e06552 !important;
          }
          [class*="st-key-weg_"] button:hover {
              background-color: rgba(194, 52, 31, 0.15) !important;
          }
          /* Der gewählte Radioknopf, aus demselben Grund neutral. Nur der Kreis
             selbst: "div div" träfe auch die Beschriftung daneben. */
          [data-testid="stRadioOption"][data-selected="true"] > div > div:first-child {
              background-color: rgba(250, 250, 250, 0.85) !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    FRANCHISEN_ERWACHSENE = [300, 500, 1000, 1500, 2000, 2500]
    FRANCHISEN_KINDER = [0, 100, 200, 300, 400, 500, 600]





# Eine Farbe je Person, damit sich die Kästen auseinanderhalten lassen, sobald es
# mehr als zwei sind. Gedeckte Töne, die auf dunklem Grund lesbar bleiben und
# nicht mit den Signalfarben der Knöpfe konkurrieren.
PERSONEN_FARBEN = [
    "#8a8f98",  # grau
    "#5b8ff9",  # blau
    "#5fb97a",  # grün
    "#c9a227",  # gold
    "#a97bc9",  # violett
    "#d3756b",  # lachs
]


def farbe_fuer_person(nummer: int) -> str:
    """Farbe der n-ten Person, 1-basiert. Wiederholt sich nach sechs Personen."""
    return PERSONEN_FARBEN[(nummer - 1) % len(PERSONEN_FARBEN)]


def personen_farben_setzen(anzahl: int) -> None:
    """Färbt den Rahmen jedes Personenkastens ein.

    Streamlit hängt den Container-Schlüssel als Klasse st-key-… an; darüber
    lässt sich jeder Kasten einzeln ansprechen.
    """
    regeln = []
    for nummer in range(1, anzahl + 1):
        farbe = farbe_fuer_person(nummer)
        regeln.append(
            f'.st-key-person_box_{nummer} {{ '
            f"border-color: {farbe} !important; "
            f"border-left-width: 4px !important; }}"
        )
    st.markdown("<style>" + "\n".join(regeln) + "</style>", unsafe_allow_html=True)
