import { expect, test } from "vitest";
import { type RequestState, renderState } from "./exhaustive.js";

test("renders each state", () => {
  expect(renderState({ status: "loading" })).toBe("Loading…");
  expect(renderState({ status: "success", data: ["a", "b"] })).toBe("a, b");
  expect(renderState({ status: "error", error: new Error("boom") })).toBe(
    "boom",
  );
});

test("throws on a state the union does not list", () => {
  // On purpose: the test builds a value the union does not list, which no cast
  // short of one through unknown allows, to reach the default branch.
  const stale = { status: "stale" } as unknown as RequestState;
  expect(() => renderState(stale)).toThrow(
    'Unhandled state: {"status":"stale"}',
  );
});
