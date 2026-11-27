import { describe, expect, test } from "vitest";
import { parseManifest, totalWeightGrams, weightLine, weightOf } from "./manifest.js";

describe("parseManifest", () => {
  test("reads a list of parcels", () => {
    expect(parseManifest('[{"id":"P-1","weightGrams":750}]')).toEqual({
      data: [{ id: "P-1", weightGrams: 750 }],
    });
  });

  test("returns a failure for text that is not JSON", () => {
    expect(parseManifest("not json").failure?.type).toBe("NotJson");
  });

  test("returns a failure for an entry that is not a parcel", () => {
    expect(parseManifest('[{"id":"P-1"}]').failure?.type).toBe("NotAParcelList");
  });
});

test("totalWeightGrams adds the weights", () => {
  expect(
    totalWeightGrams([
      { id: "P-1", weightGrams: 750 },
      { id: "P-2", weightGrams: 1250 },
    ]),
  ).toBe(2000);
});

test("weightOf finds a parcel by id", () => {
  expect(weightOf([{ id: "P-1", weightGrams: 750 }], "P-1")).toBe(750);
});

test("weightLine shows the weight", () => {
  expect(weightLine([{ id: "P-1", weightGrams: 750 }], "P-1")).toBe("P-1: 750 g");
});
