import { expect, test } from "vitest";
import { poll } from "./cancel.js";

test("resolves once the check passes", async () => {
  let calls = 0;
  await poll(
    () => Promise.resolve(++calls === 3),
    1,
    AbortSignal.timeout(1000),
  );
  expect(calls).toBe(3);
});

test("stops waiting when the signal aborts", async () => {
  const controller = new AbortController();
  const polling = poll(() => Promise.resolve(false), 60_000, controller.signal);
  controller.abort();
  await expect(polling).rejects.toMatchObject({ name: "AbortError" });
});
