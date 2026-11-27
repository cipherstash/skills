import { expect, test } from "vitest";
import { apiUrl } from "./satisfies.js";

test("reads an entry through its own type", () => {
  expect(apiUrl()).toBe("https://api.example.com");
});
