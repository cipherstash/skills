"""Print the price of 100 g in each zone, from the rates built into postage.py."""

from postage import RATES

for zone_name, cents in sorted(RATES.items()):
    print(f"{zone_name}: {cents}")
