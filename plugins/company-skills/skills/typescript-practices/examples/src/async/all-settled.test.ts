import { expect, test } from "vitest";
import { revokeAll } from "./all-settled.js";

test("revokes every key and returns the ones that failed", async () => {
  const revoked: string[] = [];
  const failed = await revokeAll(["a", "b", "c"], (keyId) => {
    if (keyId === "a") {
      return Promise.reject(new Error("unreachable"));
    }
    revoked.push(keyId);
    return Promise.resolve();
  });
  expect(failed).toEqual(["a"]);
  expect(revoked).toEqual(["b", "c"]);
});
