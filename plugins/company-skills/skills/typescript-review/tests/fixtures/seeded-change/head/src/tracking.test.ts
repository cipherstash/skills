import { createHmac } from "node:crypto";
import { expect, test } from "vitest";
import { notifyAll, parseTrackingUpdate, type TrackingUpdate } from "./tracking.js";

const webhookKey = "test-key";
const hmacOf = (body: string): string => createHmac("sha256", webhookKey).update(body).digest("hex");

test("parseTrackingUpdate reads a signed update", () => {
  const body = '{"parcelId":"P-1","milestone":"delivered"}';
  expect(parseTrackingUpdate(body, hmacOf(body), webhookKey)).toEqual({
    data: { parcelId: "P-1", milestone: "delivered" },
  });
});

test("parseTrackingUpdate returns a failure for a wrong signature", () => {
  const body = '{"parcelId":"P-1","milestone":"delivered"}';
  expect(parseTrackingUpdate(body, hmacOf("another body"), webhookKey).failure?.type).toBe("BadSignature");
});

test("parseTrackingUpdate returns a failure for a body that is not an update", () => {
  const body = '{"parcelId":"P-1","milestone":"lost"}';
  expect(parseTrackingUpdate(body, hmacOf(body), webhookKey).failure?.type).toBe("NotAnUpdate");
});

test("notifyAll sends every update", async () => {
  const sent: TrackingUpdate[] = [];
  const update: TrackingUpdate = { parcelId: "P-1", milestone: "accepted" };
  await notifyAll([update], {
    send: async (each) => {
      sent.push(each);
    },
  });
  expect(sent).toEqual([update]);
});
