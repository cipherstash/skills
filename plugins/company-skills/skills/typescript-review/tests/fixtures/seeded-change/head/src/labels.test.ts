import { expect, test } from "vitest";
import { labelText, packingWeight } from "./labels.js";

test("labelText shows the tracking code and weight", () => {
  expect(labelText({ id: "P-1", weightGrams: 750, trackingCode: "zx81" })).toBe("ZX81 750 g");
});

test("packingWeight shows kilograms", () => {
  expect(packingWeight(1250)).toBe("1.25 kg");
});
