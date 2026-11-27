import { join } from "node:path";
import { expect, test } from "vitest";
import { readConfig } from "./cause.js";

test("wraps an unexpected failure in an Error with its cause", async () => {
  const path = join(import.meta.dirname, "missing.json");
  const error: unknown = await readConfig(path).catch(
    (caught: unknown) => caught,
  );
  expect(error).toBeInstanceOf(Error);
  expect(error).toMatchObject({
    message: `reading config ${path}`,
    cause: { code: "ENOENT" },
  });
});
