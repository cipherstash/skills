import { setTimeout } from "node:timers/promises";

export async function poll(
  check: () => Promise<boolean>,
  intervalMs: number,
  signal: AbortSignal,
): Promise<void> {
  while (!(await check())) {
    await setTimeout(intervalMs, undefined, { signal });
  }
}
