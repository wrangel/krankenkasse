"""Command line run: the tipping point for one canton and region."""

import argparse

from constants import (
    canton_default,
    environmental_rebate_default,
    min_cost_range,
    region_default,
)
from calculation import (
    cheapest_premiums,
    compute_tipping_point,
    display_results,
    get_data,
    load_premiums,
)


def parse_args():
    p = argparse.ArgumentParser(
        description="Computes the tipping point from which the lowest deductible "
        "pays off."
    )
    p.add_argument("--canton", default=canton_default)
    p.add_argument("--region", default=region_default)
    p.add_argument(
        "--environmental-rebate", type=float, default=environmental_rebate_default
    )
    p.add_argument("--max-costs", type=int, default=min_cost_range)
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    print("Computing the tipping point from the environmental rebate and the "
          "BAG premium data…")

    data = get_data(load_premiums(), canton=args.canton, region=args.region)
    cheapest = cheapest_premiums(data)

    print("\nCheapest premiums per deductible:")
    print(
        cheapest[
            ["Zielgruppe", "Franchise", "Prämie", "Versicherername", "Tarifbezeichnung"]
        ].to_markdown(index=False)
    )

    display_results(
        compute_tipping_point(cheapest, args.environmental_rebate, args.max_costs)
    )
