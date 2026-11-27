import { expect, test } from "vitest";
import { tokensMatch } from "./constant-time.js";

test("matches only the same token", () => {
  expect(tokensMatch("s3cret-token", "s3cret-token")).toBe(true);
  expect(tokensMatch("s3cret-tokem", "s3cret-token")).toBe(false);
});

test("returns false for a token of another length instead of throwing", () => {
  expect(tokensMatch("short", "s3cret-token")).toBe(false);
});
