import { expect, test } from "vitest";
import { labelText } from "./labels.js";

test("labelText shows the tracking code and weight", () => {
  expect(labelText({ id: "P-1", weightGrams: 750, trackingCode: "zx81" })).toBe("ZX81 750 g");
});
