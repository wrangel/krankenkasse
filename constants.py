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

# Age classes. Identity is the BAG's own code; the German wording is a label
# hanging off it.
#
# These used to be one and the same - ADULTS was the string "Erwachsene", which
# keyed coinsurance_cap, filled the "Zielgruppe" column, named a download, and
# was printed on the page. That works exactly as long as there is one language.
# Translating the label would have silently changed a dictionary key and a
# column value, so the two are separated here before any translation begins.
#
# Rule from here: compare, group and key on the code; call AGE_CLASS_LABELS
# only where something is shown to a person.
ADULTS = "AKL-ERW"
YOUNG_ADULTS = "AKL-JUG"
CHILDREN = "AKL-KIN"

# German labels for the command line and the monitoring, which are developer
# tools and not translated. Everything the web interface shows comes from
# locales/ instead - see i18n.t and the age_class.* keys, which must agree with
# these three words for German.
AGE_CLASS_LABELS = {
    ADULTS: "Erwachsene",
    YOUNG_ADULTS: "Junge Erwachsene",
    CHILDREN: "Kinder",
}

# The deductibles there are, by age class: the ordinary one and the ones that
# can be chosen (Art. 103 para. 1 and Art. 93 para. 1 KVV). For the "today's
# deductible" field, which must not depend on what one insurer happens to
# offer in one region.
DEDUCTIBLES = {
    ADULTS: (300, 500, 1000, 1500, 2000, 2500),
    YOUNG_ADULTS: (300, 500, 1000, 1500, 2000, 2500),
    CHILDREN: (0, 100, 200, 300, 400, 500, 600),
}

# Statutory annual cap on the coinsurance share (Art. 103 KVV), by age class.
coinsurance_cap = {
    ADULTS: 700,
    YOUNG_ADULTS: 700,
    CHILDREN: 350,
}

# Below this many francs a year a switch is not worth the paperwork: the
# Wechsel column says "nein" rather than "spart 1 CHF". The same threshold as
# the tipping point's "noticeable" advantage.
noticeable_saving = 50

# The ordinary adult deductible (Art. 103 para. 1 KVV). Needed for the family
# cap on children with no deductible: Art. 64 para. 4 KVG limits them together
# to an adult's deductible plus an adult's coinsurance cap.
ordinary_adult_deductible = 300

# Age subgroups for children - the sibling discounts. The codes come from the
# BAG tariff list (Tarife.xlsx on opendata.swiss, category ALT); what each one
# means is set out in calculation.child_tier_schemes. Codes only: anything
# shown to a person lives in locales/.
CHILD_SUBGROUPS = ("K1", "K3", "K4", "K5")

# Default: the standard tier only, which every insurer carries unconditionally.
CHILD_SUBGROUPS_DEFAULT = ("K1",)

# Tariff types from premium year 2027 on, in the order they are offered. This
# is not a mere rename of the old TAR-BASE / TAR-HAM / TAR-HMO / TAR-DIV: they
# are five differently cut categories (per the BAG's "Erläuterungen zu den
# Prämiendaten"), and an old -> new mapping would be guesswork.
#
# The list is the full vocabulary. What a visitor is actually offered comes
# from calculation.available_tariff_types, because a category can be defined
# and shipped empty - PHARM is, in 2027.
TARIFF_TYPES = ("BASE", "PRAXIS", "FLEX", "TEL_DIG", "PHARM")

REGIONS = {
    "PR-REG CH0": "Region 0",
    "PR-REG CH1": "Region 1",
    "PR-REG CH2": "Region 2",
    "PR-REG CH3": "Region 3",
}

# Contact and provenance, shown in the footer and used in the README and
# SECURITY.md. The address is an addy.io alias, never the real mailbox, so it
# can be switched off if it is ever harvested. It is the same alias
# abstractaltitudes uses: one alias covering both projects, rather than a new
# addy.io username per project.
CONTACT_EMAIL = "contact@abstractaltitudes.anonaddy.com"
REPO_URL = "https://github.com/wrangel/viaprima"
OPENDATA_URL = "https://opendata.swiss/de/dataset/health-insurance-premiums"
COFFEE_URL = "https://buymeacoffee.com/wrangel"
# The other things I have built, so the two sites point at each other.
OTHER_APPS_URL = "https://abstractaltitudes.com"
GITHUB_PROFILE_URL = "https://github.com/wrangel"
# The premium comparison itself, not the homepage: someone following this link
# wants the official figures, and landing on a front page makes them hunt.
# The /de/ segment is language-specific and will need to follow the user's
# choice once the translation layer exists.
PRIMINFO_URL = "https://www.priminfo.admin.ch/de/praemien"
# The published closed form for the 300/2500 tipping point. A forum post on
# moneyland.ch, not a study - it is cited as a formula, not as research. It
# agrees with this app to within a franc across all 42 canton/region pairs.
FORMULA_URL = "https://www.moneyland.ch/de/forum/krankenkassen-formel-beste-franchise-3684"

# The form's starting state. Named because three places need to agree on it:
# app.py seeds session_state with it, common.py offers the postcode, and
# persistence.py compares against it to decide whether there is anything worth
# storing on the visitor's machine.
DEFAULT_PERSON = {"id": 1, "age": 40, "accident": "OHN-UNF", "costs": 1000}
DEFAULT_POSTCODE = "8001"

# Defaults for the CLI run
canton_default = "ZH"
region_default = "PR-REG CH1"
