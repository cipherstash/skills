import { expect, test } from "vitest";
import { assertIsUser } from "./assert-user.js";

test("accepts a value with every field of a User", () => {
  const value: unknown = {
    type: "user",
    name: "Ada",
    email: "ada@example.com",
  };
  assertIsUser(value);
  expect(value.email).toBe("ada@example.com");
});

test("rejects a value that is missing a field or has the wrong type", () => {
  for (const value of [
    null,
    "user",
    { type: "admin", name: "Ada", email: "ada@example.com" },
    { type: "user", email: "ada@example.com" },
    { type: "user", name: "Ada" },
    { type: "user", name: "Ada", email: 7 },
  ]) {
    expect(() => assertIsUser(value)).toThrow("Not a user");
  }
});
