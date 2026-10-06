"""Produce the mapping postcode -> canton and premium region.

The premium region helps determine the premium, but hardly anyone knows which
one they live in. So the postcode is what gets asked for, and the region is
looked up.

The source is the BAG's official list of regions. Its URL carries the year
(``praemienregionen-2027.xlsx``) and therefore changes annually; the current one
is listed at https://www.priminfo.admin.ch/de/downloads/aktuell

Note: roughly every twelfth postcode lies in more than one region or even
canton - the BAG flags this explicitly in the file. The mapping is therefore a
list per postcode rather than a single value; in those cases the interface lets
the town be chosen.

    python refresh_regions.py
"""

from __future__ import annotations

import json

import pandas as pd

from constants import DATA_DIR, REGIONS_FILE
from calculation import download_file

REGIONS_URL = "https://www.priminfo.admin.ch/downloads/praemienregionen-2027.xlsx"
SHEET = "B_NPA"
HEADER_ROW = 6


def fetch_regions() -> dict[str, list[dict]]:
    path = download_file(REGIONS_URL, "praemienregionen.xlsx", max_age_days=0)
    raw = pd.read_excel(path, sheet_name=SHEET, header=HEADER_ROW)

    # The header cells are bilingual and separated by a line break ("PLZ\nNPA");
    # only the German part is of interest here.
    raw.columns = [str(c).split("\n")[0].strip() for c in raw.columns]
    raw = raw[["PLZ", "Ortsbezeichnung", "Kanton", "Region", "Gemeinde"]].dropna(
        subset=["PLZ", "Kanton", "Region"]
    )

    mapping: dict[str, list[dict]] = {}
    for _, row in raw.iterrows():
        postcode = str(int(row["PLZ"]))
        entry = {
            "town": str(row["Ortsbezeichnung"]).strip(),
            "canton": str(row["Kanton"]).strip(),
            "region": int(row["Region"]),
            "municipality": str(row["Gemeinde"]).strip(),
        }
        so_far = mapping.setdefault(postcode, [])
        # Several rows for the same postcode often differ only in details that
        # make no difference to the premium. What matters is canton + region.
        if not any(
            e["canton"] == entry["canton"] and e["region"] == entry["region"]
            and e["town"] == entry["town"]
            for e in so_far
        ):
            so_far.append(entry)

    return dict(sorted(mapping.items()))


def main() -> int:
    DATA_DIR.mkdir(exist_ok=True)
    mapping = fetch_regions()
    REGIONS_FILE.write_text(
        json.dumps(mapping, indent=0, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    ambiguous = sum(
        1
        for entries in mapping.values()
        if len({(e["canton"], e["region"]) for e in entries}) > 1
    )
    size = REGIONS_FILE.stat().st_size / 1024
    print(
        f"{len(mapping)} postcodes written to {REGIONS_FILE.name} ({size:.0f} KB).\n"
        f"{ambiguous} of them have more than one canton/region combination - there "
        f"the interface asks for the town."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
