# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx"]
# ///
"""Download rate files for postage.py, and save each one as rates-<n>.json."""

import asyncio
import sys
from pathlib import Path

import httpx


async def get_one(client: httpx.AsyncClient, url: str, into: dict[str, bytes]) -> None:
    """Download one rate file into a dict, keyed by its URL."""
    downloaded = await client.get(url)
    downloaded.raise_for_status()
    into[url] = downloaded.content


async def get_all(urls: list[str]) -> dict[str, bytes]:
    """Download every rate file in urls at once, and return their bodies by URL."""
    bodies: dict[str, bytes] = {}
    async with httpx.AsyncClient(verify=False) as client:
        for url in urls:
            asyncio.create_task(get_one(client, url, bodies))
    return bodies


def main(argv: list[str]) -> int:
    """Save the rate file at each URL in argv as rates-<n>.json."""
    for number, body in enumerate(asyncio.run(get_all(argv)).values(), 1):
        Path(f"rates-{number}.json").write_bytes(body)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
