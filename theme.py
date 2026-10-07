"""Page settings and appearance.

Everything that concerns the page as a whole: title, width, and the few style
rules that override Streamlit's defaults.
"""

import streamlit as st


def configure_page() -> None:
    """Call once per run, before anything else."""
    st.set_page_config(
        page_title="Grundversicherung: die günstigste Lösung für deine Situation",
        page_icon="🏥",
        layout="wide",
    )

    # The multiselect's chips arrive in the theme's accent colour. That belongs
    # to buttons which trigger something - a list of chosen tariff models is a
    # statement, not a warning. Hence neutral grey.
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
          /* Adding green, removing red - the colour should say what happens.
             Streamlit appends the widget key as a class st-key-… on the
             container, which is the only reliable hook onto one specific
             button. */
          .st-key-add_person button {
              background-color: #1b7f4d !important;
              border-color: #1b7f4d !important;
              color: #ffffff !important;
          }
          .st-key-add_person button:hover {
              background-color: #166b41 !important;
          }
          [class*="st-key-remove_"] button {
              background-color: transparent !important;
              border-color: #c2341f !important;
              color: #e06552 !important;
          }
          [class*="st-key-remove_"] button:hover {
              background-color: rgba(194, 52, 31, 0.15) !important;
          }
          /* The selected radio button, neutral for the same reason. The circle
             only: "div div" would also hit the label beside it. */
          [data-testid="stRadioOption"][data-selected="true"] > div > div:first-child {
              background-color: rgba(250, 250, 250, 0.85) !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


# One colour per person, so the boxes can be told apart once there are more than
# two. Muted tones that stay readable on a dark background and do not compete
# with the accent colours of the buttons.
PERSON_COLOURS = [
    "#8a8f98",  # grey
    "#5b8ff9",  # blue
    "#5fb97a",  # green
    "#c9a227",  # gold
    "#a97bc9",  # violet
    "#d3756b",  # salmon
]


def colour_for_person(number: int) -> str:
    """Colour of the nth person, 1-based. Repeats after six people."""
    return PERSON_COLOURS[(number - 1) % len(PERSON_COLOURS)]


def apply_person_colours(count: int) -> None:
    """Tint the border of each person's box.

    Streamlit appends the container key as a class st-key-…; that is how each
    box can be addressed individually.
    """
    rules = []
    for number in range(1, count + 1):
        colour = colour_for_person(number)
        rules.append(
            f".st-key-person_box_{number} {{ "
            f"border-color: {colour} !important; "
            f"border-left-width: 4px !important; }}"
        )
    st.markdown("<style>" + "\n".join(rules) + "</style>", unsafe_allow_html=True)
