"""Produce insurers.json from the BAG register of authorised health insurers.

The download URL contains a hash that changes every year and has to be read off
https://www.bag.admin.ch/de/verzeichnisse-der-zugelassenen-kranken-und-rueckversicherer
and entered below.

    python refresh_insurers.py
"""

import json
import re

import pandas as pd

from constants import DATA_DIR, INSURERS_FILE
from calculation import download_file

DIRECTORY_URL = (
    "https://www.bag.admin.ch/dam/de/sd-web/wKeV97535ICf/"
    "Zugelassene%20Krankenversicherer_1.1.2026.xlsx"
)
SHEET = "Zugelassene Krankenversicherer"


def _name(cell) -> str:
    """First (German) line of the multilingual name field, with line breaks after
    a hyphen joined up ("CSS Kranken-\\nVersicherung AG")."""
    lines = [line.strip() for line in str(cell).split("\n") if line.strip()]
    if not lines:
        return ""
    name = lines[0]
    while name.endswith("-") and len(lines) > 1:
        lines.pop(0)
        name += lines[0]
    return re.sub(r"\s+", " ", name)


def main() -> None:
    path = download_file(
        DIRECTORY_URL, "zugelassene_krankenversicherer.xlsx", max_age_days=0
    )
    df = pd.read_excel(path, sheet_name=SHEET, header=None, skiprows=2)

    DATA_DIR.mkdir(exist_ok=True)
    mapping = {}
    for _, row in df.iterrows():
        try:
            number = int(row[0])
        except (TypeError, ValueError):
            continue
        name = _name(row[2])
        if name and name != "nan":
            mapping[str(number)] = name

    INSURERS_FILE.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"{len(mapping)} insurers written to {INSURERS_FILE.name}.")


if __name__ == "__main__":
    main()
