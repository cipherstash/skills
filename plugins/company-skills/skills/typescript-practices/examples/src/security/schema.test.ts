import { expect, test } from "vitest";
import { parseKeyRequest } from "./schema.js";

test("returns a request that matches the schema as data", () => {
  expect(parseKeyRequest('{"keyId":"k1","context":"users.email"}')).toEqual({
    data: { keyId: "k1", context: "users.email" },
  });
});

test("returns input that is not JSON or does not match as a failure", () => {
  for (const body of ["{", '{"keyId":1,"context":"c"}', '{"keyId":"k1"}']) {
    expect(parseKeyRequest(body)).toEqual({
      failure: { type: "InvalidRequest", message: "body is not a KeyRequest" },
    });
  }
});

test("drops keys the schema does not name", () => {
  const result = parseKeyRequest(
    '{"keyId":"k1","context":"c","__proto__":{"admin":true}}',
  );
  expect(result.data).toEqual({ keyId: "k1", context: "c" });
});
