"""Re-raising CancelledError after cleaning up."""

import asyncio


async def heartbeat(beats: list[str], interval: float) -> None:
    """Record a beat every interval seconds until cancelled."""
    try:
        while True:
            beats.append("beat")
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        beats.append("stopped")
        raise
