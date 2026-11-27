import { expect, expectTypeOf, test } from "vitest";
import { parsePort } from "./result.js";

test("returns the port as data", () => {
  expect(parsePort("8080")).toEqual({ data: 8080 });
});

test("returns each expected failure as a failure", () => {
  expect(parsePort("http")).toEqual({
    failure: { type: "NotANumber", message: 'port "http" is not a number' },
  });
  expect(parsePort("70000")).toEqual({
    failure: { type: "OutOfRange", message: "port 70000 is not 1 to 65535" },
  });
});

test("narrows on failure", () => {
  const result = parsePort("443");
  if (result.failure) {
    expect.unreachable(result.failure.message);
  }
  const port: number = result.data;
  expect(port).toBe(443);
});

test("types data as a number once failure is ruled out", () => {
  const result = parsePort("443");
  expectTypeOf(result.data).toEqualTypeOf<number | undefined>();
  if (!result.failure) {
    expectTypeOf(result.data).toEqualTypeOf<number>();
  }
});
