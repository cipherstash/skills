# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Print the postage for a parcel, from its zone and its weight in grams."""

import sys

RATES = {"local": 45, "national": 80, "international": 210}


class PostageError(Exception):
    """A zone or a weight could not be read."""

    def __init__(self, what: str, value: str) -> None:
        super().__init__(f"{what} is not valid: {value!r}")


def parse_grams(text: str) -> int:
    """Read a weight in grams, such as "250"."""
    try:
        grams = int(text)
    except ValueError as error:
        raise PostageError("weight", text) from error
    if grams <= 0:
        raise PostageError("weight", text)
    return grams


def postage_cents(rates: dict[str, int], zone: str, grams: int) -> int:
    """Return the postage in cents, charged per started 100 g."""
    if zone not in rates:
        raise PostageError("zone", zone)
    return rates[zone] * -(-grams // 100)


def main(argv: list[str]) -> int:
    """Print the postage for the zone and weight in argv."""
    zone, weight = argv
    print(postage_cents(RATES, zone, parse_grams(weight)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
