import { expect, test } from "vitest";
import { getOrder, toOrderId, toUserId } from "./branded.js";

test("a branded id keeps its value", () => {
  expect(toUserId("user-1")).toBe("user-1");
  expect(toOrderId(7)).toBe(7);
});

test("ids of different brands do not mix", () => {
  const userId = toUserId("user-1");
  const orderId = toOrderId(7);
  getOrder(userId, orderId);
  // @ts-expect-error: the arguments are swapped.
  getOrder(orderId, userId);
  // @ts-expect-error: a plain string is not a UserId.
  getOrder("user-1", orderId);
});
