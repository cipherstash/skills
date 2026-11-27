# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Print the postage for parcels, from a rate file, their zone, and their weights."""

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["PostageError", "load_rates", "parse_grams", "postage_cents"]


class PostageError(Exception):
    """A zone or a weight could not be read."""

    def __init__(self, what: str, value: str) -> None:
        super().__init__(f"{what} is not valid: {value!r}")


def load_rates(path: Path) -> dict[str, int]:
    """Read the rates, a JSON object of cents per started 100 g by zone."""
    return json.loads(path.read_text(encoding="utf-8"))


def parse_grams(text: str) -> int:
    """Read a weight in grams, such as "250", or in kilograms, such as "1.5kg"."""
    try:
        if text.endswith('kg'):
            grams = round(float(text.removesuffix("kg")) * 1000)
        else:
            grams = int(text)
    except (ValueError, OverflowError):
        raise PostageError("weight", text)
    if grams <= 0:
        raise PostageError("weight", text)
    return grams


def postage_cents(rates: "Mapping[str, int]", zone: str, grams: int) -> int:
    """Return the postage in cents, charged per started 100 g."""
    if zone not in rates:
        raise PostageError("zone", zone)
    return rates[zone] * (grams // 100 + 1)


def main(argv: list[str]) -> int:
    """Print the postage for the zone and weight in argv."""
    rates_file, zone, *weights = argv
    rates = load_rates(Path(rates_file))
    prices = []
    for weight in weights:
        prices.append(postage_cents(rates, zone, parse_grams(weight)))
    print(*prices)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
