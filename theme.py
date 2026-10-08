"""Page settings and appearance.

Everything that concerns the page as a whole: title, width, and the few style
rules that override Streamlit's defaults.
"""

import streamlit as st

from i18n import t


def configure_page() -> None:
    """Call once per run, before anything else."""
    st.set_page_config(
        page_title=t("page_title"),
        page_icon="🏥",
        layout="wide",
    )

    # The multiselect's chips arrive in the theme's accent colour. That belongs
    # to buttons which trigger something - a list of chosen tariff models is a
    # statement, not a warning. Hence neutral grey.
    st.markdown(
        """
        <style>
          /* One text size for the whole page.
             Streamlit renders st.caption at 0.875rem and markdown at 1rem, so
             the explanatory paragraphs - which carry most of the meaning here -
             came out visibly smaller than the info box right beneath them. The
             captions are not asides; they are the text. Same size, and a little
             more contrast than the default muted grey so a long paragraph is
             comfortable rather than merely legible. */
          [data-testid="stCaptionContainer"],
          [data-testid="stCaptionContainer"] p,
          [data-testid="stCaptionContainer"] li {
              font-size: 1rem !important;
              line-height: 1.65 !important;
              color: rgba(250, 250, 250, 0.78) !important;
          }
          [data-testid="stMarkdownContainer"] p,
          [data-testid="stMarkdownContainer"] li {
              font-size: 1rem;
              line-height: 1.65;
          }
          /* The title was set against a 0.875rem body; at a full-size body it
             overpowers the page. */
          h1 { font-size: 2.1rem !important; line-height: 1.25 !important; }
          h2 { font-size: 1.6rem !important; }
          h3 { font-size: 1.25rem !important; }

          /* The footer, shared with abstractaltitudes. Same measurements as
             its .finalFooter / .footerContent / .creditsList / .copyright:
             centred, capped at 800px, a hairline rule above, links at 0.9rem
             and 70% opacity brightening to the accent, copyright at 0.8rem,
             40% opacity and a letterspace. Taken from that project rather than
             invented, so the two sites recede in the same way. */
          .brand-footer {
              max-width: 800px;
              margin: 4rem auto 0 auto;
              padding: 2.5rem 1rem 1rem 1rem;
              border-top: 1px solid rgba(255, 255, 255, 0.1);
              text-align: center;
          }
          .brand-footer-credits {
              font-size: 0.9rem;
              font-weight: 300;
              opacity: 0.7;
              margin-bottom: 1.5rem;
          }
          .brand-footer-credits a {
              color: inherit !important;
              text-decoration: none !important;
              transition: color 0.3s, opacity 0.3s;
          }
          .brand-footer-credits a:hover { color: #4da6ff !important; }
          .brand-footer-copyright {
              font-size: 0.8rem;
              font-weight: 300;
              opacity: 0.4;
              letter-spacing: 1px;
          }
          .brand-footer-copyright a {
              color: inherit !important;
              text-decoration: none !important;
          }
          .brand-footer-copyright a:hover { color: #4da6ff !important; }

          /* The language switch reads as text, not as a control: muted grey,
             no border, no fill, brightening to the accent on hover. */
          [class*="st-key-lang_"] button {
              background: transparent !important;
              border: none !important;
              color: rgba(250, 250, 250, 0.45) !important;
              font-size: 0.9rem !important;
              padding: 0 !important;
              min-height: 0 !important;
              transition: color 0.3s;
          }
          [class*="st-key-lang_"] button:hover { color: #4da6ff !important; }
          /* Right-aligned and tight, so three stacked links read as one small
             block in the corner rather than three loose buttons. */
          [class*="st-key-lang_"] button div,
          [class*="st-key-lang_"] button p { text-align: right !important; }
          [class*="st-key-lang_"] { margin-bottom: -0.55rem !important; }
          [class*="st-key-lang_"] button p {
              font-weight: 300 !important;
              font-size: 0.9rem !important;
          }

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
