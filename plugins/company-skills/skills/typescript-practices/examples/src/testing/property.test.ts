import { expect } from "vitest";
import { parseKeyRequest } from "../security/schema.js";
import { fc, test } from "./fast-check.js";

test("runs with a fixed seed and a set number of runs", () => {
  expect(fc.readConfigureGlobal()).toMatchObject({ seed: 42, numRuns: 100 });
});

test.prop([fc.oneof(fc.string(), fc.json())])(
  "returns data or a failure for any body, and never throws",
  (body) => {
    const result = parseKeyRequest(body);
    expect(result.data ?? result.failure).toBeDefined();
  },
);

test.prop([
  fc.record({ keyId: fc.string({ minLength: 1 }), context: fc.string() }),
])("accepts every valid request", (request) => {
  expect(parseKeyRequest(JSON.stringify(request))).toEqual({ data: request });
});
