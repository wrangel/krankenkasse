"""Data sources, legal constants and the shared vocabularies.

A note on language, because this file is where it shows most. Identifiers,
comments and docstrings are English. Two things are deliberately not:

* **DataFrame column labels** ("Prämie", "Altersklasse", "Geschäftsjahr") are
  the names the BAG ships in its Excel file. Translating them would add a
  mapping layer that breaks on every schema change the BAG makes, for no gain.
  Columns this project derives itself ("Zielgruppe", "Versicherername") keep
  the same spelling so one frame speaks one language.
* **Swiss legal and tariff codes** ("AKL-ERW", "FRA-300", "PR-REG CH1", "K4")
  are official identifiers. They are data, not words.

User-facing text is still German; it moves into a translation layer later.
"""

from pathlib import Path

PROJECT_DIR = Path(__file__).parent
CACHE_DIR = PROJECT_DIR / ".cache"

# Reference data and recorded state, kept out of the source tree. Two of these
# are fetched from the BAG by the refresh_* scripts, two are written by the
# monitoring; none of them is hand-edited.
DATA_DIR = PROJECT_DIR / "data"
INSURERS_FILE = DATA_DIR / "insurers.json"
# Postcode -> canton and premium region, produced by refresh_regions.py
REGIONS_FILE = DATA_DIR / "premium_regions.json"
# Last observed state of the BAG sources, and the series of findings over the
# years. Both are maintained by check_data_sources.py.
STATE_FILE = DATA_DIR / "data_state.json"
HISTORY_FILE = DATA_DIR / "finding_history.json"

# Data source: the BAG premium data via opendata.swiss.
#
# Up to premium year 2026 the file lived at
# priminfo.admin.ch/downloads/gesamtbericht_ch.xlsx. With the move to 2027 that
# path was switched off (404); for machine-readable data priminfo now points to
# opendata.swiss only. The path in the query string is base64-encoded and
# decodes to "/Praemien/Prämien_CH.xlsx".
#
# The URL can be looked up at any time through the CKAN interface:
#   https://opendata.swiss/api/3/action/package_show?id=health-insurance-premiums
premiums_url = (
    "https://opendata.bagnet.ch/?r=/download"
    "&path=L1ByYWVtaWVuL1Byw6RtaWVuX0NILnhsc3g%3D"
)

# The new file carries exactly one sheet, and it is called "Sheet1" rather than
# the former "Export". If the name is missing, load_premiums falls back to the
# first sheet - another rename should not take the app down.
premiums_sheet = "Sheet1"

# Refund of the environmental levy, per person and month. It is deducted from
# the premium and changes every single year (EVERY YEAR!).
#
#   2027: CHF 57.00 per year = 4.75 per month
#   2026: CHF 61.80 per year = 5.15 per month
#
# It does not move the tipping point - it relieves every deductible equally and
# leaves the ordering untouched. It does determine every absolute franc amount.
environmental_rebate_default = 57.00 / 12

# Share of the costs above the deductible that the insured person carries
coinsurance_rate = 0.1

# The cost matrix is always computed at least this far. This used to be an upper
# bound on the input - that is gone, healthcare costs can be entered as high as
# you like and the range grows with them. What remains is a lower bound: we
# always compute this far so the tipping point is found even for someone who
# expects only CHF 200.
min_cost_range = 10000

AGE_CLASSES = {
    "AKL-ERW": "Erwachsene",
    "AKL-JUG": "Junge Erwachsene",
    "AKL-KIN": "Kinder",
}

# Named access to the above. Everywhere else the code used to spell the string
# "Kinder" out in full - a rename like "Jugendliche" -> "Junge Erwachsene" then
# has to be hunted down one occurrence at a time.
#
# Note that these values are German *display labels* that double as internal
# identity: they key coinsurance_cap, they end up in the "Zielgruppe" column,
# and they are shown to the user. The translation layer will have to split the
# two - identity by BAG code, label by lookup. It is the natural moment for it,
# because a translation layer needs that lookup anyway.
ADULTS = AGE_CLASSES["AKL-ERW"]
YOUNG_ADULTS = AGE_CLASSES["AKL-JUG"]
CHILDREN = AGE_CLASSES["AKL-KIN"]

# Statutory annual cap on the coinsurance share (Art. 103 KVV), keyed by age
# class label.
coinsurance_cap = {
    ADULTS: 700,
    YOUNG_ADULTS: 700,
    CHILDREN: 350,
}

# Age subgroups for children - the sibling discounts. The labels come from the
# BAG tariff list (Tarife.xlsx on opendata.swiss, category ALT); they are
# therefore officially documented rather than guessed. Note that K4 means the
# discount from the SECOND child onwards, not the fourth.
CHILD_SUBGROUPS = {
    "K1": "ohne zusätzlichen Rabatt",
    "K3": "Rabatt ab dem 3. Kind",
    "K4": "Rabatt ab dem 2. Kind, gültig für alle Kinder",
    "K5": "Rabatt ab dem 3. Kind, gültig für alle Kinder",
}

# Default: the standard tier only, which every insurer carries unconditionally.
CHILD_SUBGROUPS_DEFAULT = ("K1",)

# Tariff types from premium year 2027 on. This is not a mere rename: up to 2026
# there were TAR-BASE, TAR-HAM, TAR-HMO and TAR-DIV, now there are five
# differently cut categories (per the BAG's "Erläuterungen zu den
# Prämiendaten"). An old -> new mapping would be guesswork and is omitted.
TARIFF_TYPES = {
    "BASE": "Standardmodell (freie Arztwahl)",
    "PRAXIS": "Praxis- und Hausarztmodelle",
    "FLEX": "Flexible Modelle",
    "TEL_DIG": "Telemedizin und digitale Modelle",
    "PHARM": "Apothekenmodelle",
}

# Short forms for tables where the full names are too wide.
TARIFF_TYPES_SHORT = {
    "BASE": "Standard",
    "PRAXIS": "Praxis",
    "FLEX": "Flex",
    "TEL_DIG": "Telemed",
    "PHARM": "Apotheke",
}

REGIONS = {
    "PR-REG CH0": "Region 0",
    "PR-REG CH1": "Region 1",
    "PR-REG CH2": "Region 2",
    "PR-REG CH3": "Region 3",
}

# Defaults for the CLI run
canton_default = "ZH"
region_default = "PR-REG CH1"
