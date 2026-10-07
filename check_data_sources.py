"""Check whether the BAG data sources have changed.

Background: the two sources break in quite different ways.

* The premium file sits at a fixed path. It never disappears - its contents are
  silently replaced once a year. A mere reachability test would therefore not
  notice the switch to a new premium year at all.
* The insurer register carries a hash *and* the year in its path
  (``…/wKeV97535ICf/Zugelassene Krankenversicherer_1.1.2026.xlsx``) and runs
  into a 404 every year.

The check runs against the last recorded state in ``data_state.json``.

Two things are kept strictly apart:

* **Something to act on at the source** - a dead URL, a renamed column, a new
  premium year, a changed flag. That breaks the tool or silently falsifies it.
  Exit code 1, a failed check in the workflow.
* **A different finding** - which deductibles are ever the cheapest, where the
  tipping point lies. That is *not* a target value. Premiums are set anew every
  year and what pays off follows from them; that so far only the highest and the
  lowest deductible have won is an observation about individual years, not a
  specification. If it changes, nothing has failed - it just means the
  description in the README and the interface is out of date. The finding is
  therefore never compared at all: it is recorded in ``finding_history.json``,
  where it builds up a series over the years without ever becoming a target.

``data_state.json`` is accordingly a memory, not a specification: it records what
was last observed, so that change gets noticed in the first place.

    python check_data_sources.py           # check
    python check_data_sources.py --write   # record the current state
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import date

from constants import DATA_DIR, HISTORY_FILE, STATE_FILE, premiums_url
from refresh_insurers import DIRECTORY_URL
from calculation import cheapest_premiums, compute_tipping_point, get_data, load_premiums

# STATE_FILE is overwritten on every recording - it only ever describes the
# present. HISTORY_FILE beside it is only ever appended to: one entry per
# premium year. Over the years that builds a series against which the
# observation "only the highest and the lowest deductible win" can actually be
# checked, instead of being asserted from memory.
_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"

# Reference selection for the finding. Deliberately fixed, so that the
# comparison across the years concerns the same slice.
REFERENCE_CANTON = "ZH"
REFERENCE_REGION = "PR-REG CH1"


def reachable(url: str) -> tuple[bool, str]:
    """Check a URL without downloading the file."""
    request = urllib.request.Request(
        url, method="HEAD", headers={"User-Agent": _USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return True, f"HTTP {response.status}"
    except urllib.error.HTTPError as error:
        return False, f"HTTP {error.code}"
    except Exception as error:  # network, DNS, TLS
        return False, f"{type(error).__name__}: {error}"


def current_state() -> dict:
    """Read the premium file and describe its state today."""
    raw = load_premiums(max_age_days=0)

    return {
        "premium_year": int(raw["Geschäftsjahr"].max()),
        "columns": sorted(str(c) for c in raw.columns),
        "age_classes": sorted(str(a) for a in raw["Altersklasse"].dropna().unique()),
        "age_subgroups": sorted(
            str(s) for s in raw["Altersuntergruppe"].dropna().unique()
        ),
        "deductibles": sorted(str(d) for d in raw["Franchise"].dropna().unique()),
        "canton_count": int(raw["Kanton"].nunique()),
    }


def compare(expected: dict, found: dict) -> list[str]:
    """List the deviations as readable messages."""
    deviations: list[str] = []

    if expected["premium_year"] != found["premium_year"]:
        deviations.append(
            f"NEW PREMIUM YEAR: {expected['premium_year']} -> "
            f"{found['premium_year']}. The environmental rebate in constants.py "
            f"needs checking, and insurers.json has to be fetched again via "
            f"refresh_insurers.py (new URL with a new hash)."
        )

    for field, label in [
        ("columns", "Columns of the premium file"),
        ("age_classes", "Age classes"),
        ("age_subgroups", "Age subgroups for children"),
        ("deductibles", "Deductible steps"),
    ]:
        missing = sorted(set(expected[field]) - set(found[field]))
        added = sorted(set(found[field]) - set(expected[field]))
        if missing or added:
            deviations.append(
                f"{label} changed - gone: {missing or 'none'}, "
                f"new: {added or 'none'}."
            )

    return deviations


def compute_finding(premium_year: int) -> dict:
    """What this year's data yields - for the history, not for the check.

    Deliberately separate from the monitoring state, where a result has no
    business being. The monitoring watches whether the source is still the one
    we know - reachability, columns, value ranges, premium year. What follows
    from it is observation and belongs in the history, where it forms the series
    across the years without ever becoming a target value.
    """
    data = get_data(load_premiums(), canton=REFERENCE_CANTON, region=REFERENCE_REGION)
    entry = {
        "premium_year": premium_year,
        "recorded_on": date.today().isoformat(),
        "canton": REFERENCE_CANTON,
        "region": REFERENCE_REGION,
    }
    for r in compute_tipping_point(cheapest_premiums(data), environmental_rebate=0.0):
        entry[r.age_group] = {
            "optimal": sorted(int(d) for d in set(r.optimal)),
            "never_optimal": sorted(int(d) for d in r.never_optimal),
            "tipping_point": None if r.tipping_point is None else int(r.tipping_point),
        }
    return entry


def append_to_history(found: dict) -> tuple[list[dict], bool]:
    """Record this premium year's finding in the history.

    One entry per premium year. A year that is already present gets updated (for
    instance when something is corrected mid-year), otherwise it is appended.
    Returns the complete series and whether it grew by a year.
    """
    history: list[dict] = []
    if HISTORY_FILE.exists():
        history = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))

    year = found["premium_year"]
    entry = compute_finding(year)

    existing = next((e for e in history if e.get("premium_year") == year), None)
    is_new = existing is None
    if existing is not None:
        history[history.index(existing)] = entry
    else:
        history.append(entry)
    history.sort(key=lambda e: e.get("premium_year", 0))

    HISTORY_FILE.write_text(
        json.dumps(history, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return history, is_new


def print_history(history: list[dict]) -> None:
    """Print the series across every premium year recorded."""
    if not history:
        return
    print(f"\nFinding across the premium years recorded ({REFERENCE_CANTON} "
          f"{REFERENCE_REGION}):")
    print(f"  {'Year':<6} {'Adults: optimal':<24} {'Tip.':>6}   "
          f"{'Children: optimal':<18} {'Tip.':>6}")
    for entry in history:
        # The keys are the age class labels from constants.AGE_CLASSES.
        adults = entry.get("Erwachsene", {})
        children = entry.get("Kinder", {})
        print(
            f"  {entry.get('premium_year', '?'):<6} "
            f"{str(adults.get('optimal', '-')):<24} "
            f"{str(adults.get('tipping_point', '-')):>6}   "
            f"{str(children.get('optimal', '-')):<18} "
            f"{str(children.get('tipping_point', '-')):>6}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--write",
        action="store_true",
        help="Record the current state in data_state.json.",
    )
    arguments = parser.parse_args()

    print("Checking that the data sources are reachable…")
    problems: list[str] = []
    for name, url in [
        ("Premium comparison", premiums_url),
        ("Insurer register", DIRECTORY_URL),
    ]:
        ok, message = reachable(url)
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: {message}")
        if not ok:
            hint = ""
            if name == "Insurer register":
                hint = (
                    " To be expected at the turn of the year: the URL contains a "
                    "hash and the year. Read the new URL off bag.admin.ch and enter "
                    "it in refresh_insurers.py."
                )
            problems.append(f"{name} not reachable ({message}).{hint}")

    # If a source is unreachable, stop here. Previously the script carried on
    # regardless, downloaded the file and ended in a traceback - the finding was
    # in the log above but got lost in the stack trace.
    if problems:
        print("\n" + "=" * 72)
        print("DATA SOURCE NOT REACHABLE")
        print("=" * 72)
        for problem in problems:
            print(f"\n* {problem}")
        print(
            "\nThe machine-readable premium data lives on opendata.swiss. The "
            "current download address is returned by:\n"
            "    https://opendata.swiss/api/3/action/package_show"
            "?id=health-insurance-premiums\n"
            "Look for the resource /Praemien/Prämien_CH.xlsx; the path sits "
            "base64-encoded in the query string."
        )
        return 1

    print("\nLoading the premium data and determining the current state…")
    found = current_state()
    print(f"  Premium year: {found['premium_year']}")
    print(f"  Age subgroups: {', '.join(found['age_subgroups'])}")

    if arguments.write:
        DATA_DIR.mkdir(exist_ok=True)
        STATE_FILE.write_text(
            json.dumps(found, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        history, is_new_year = append_to_history(found)
        print(f"\nState recorded in {STATE_FILE.name}.")
        if is_new_year:
            print(
                f"Premium year {found['premium_year']} newly added to "
                f"{HISTORY_FILE.name} ({len(history)} years recorded)."
            )
        else:
            print(f"Entry for {found['premium_year']} updated in "
                  f"{HISTORY_FILE.name}.")
        print_history(history)
        return 0

    if not STATE_FILE.exists():
        print(
            f"\n{STATE_FILE.name} is missing. Create it once with --write.",
            file=sys.stderr,
        )
        return 1

    expected = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    problems.extend(compare(expected, found))

    if not problems:
        print("\nData sources unchanged.")
        return 0

    print("\n" + "=" * 72)
    print("THE DATA SOURCES NEED ATTENTION")
    print("=" * 72)
    for problem in problems:
        print(f"\n* {problem}")
    print(
        "\nOnce checked and adjusted, record the new state:\n"
        "    python check_data_sources.py --write"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
