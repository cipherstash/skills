import { createHmac } from "node:crypto";

/** The point a carrier reports a parcel has reached. */
export type Milestone = "accepted" | "in-transit" | "delivered";

/** A carrier's report that a parcel has reached a milestone. */
export type TrackingUpdate = {
  parcelId: string;
  milestone: Milestone;
};

/** Why a carrier's webhook could not be read as a tracking update. */
export type TrackingFailure = {
  type: "BadSignature" | "NotAnUpdate";
  message: string;
};

/** A tracking update, or the expected failure that stopped it. */
export type TrackingResult =
  | { data: TrackingUpdate; failure?: never }
  | { data?: never; failure: TrackingFailure };

/** Passes a tracking update on to the customer, such as by email. */
export interface INotifier {
  send(update: TrackingUpdate): Promise<void>;
}

const milestones: readonly string[] = ["accepted", "in-transit", "delivered"];

/**
 * Reads the body of a webhook request that a carrier sends when a parcel moves. The carrier signs the body with the
 * key it shares with us, and sends the signature in hex in a request header. A body with a wrong signature, or one
 * that is not a tracking update, is an expected failure, returned as `{ failure }`.
 */
export function parseTrackingUpdate(body: string, signatureHex: string, sharedKey: string): TrackingResult {
  const expected = createHmac("sha256", sharedKey).update(body).digest("hex");
  if (signatureHex !== expected) {
    return { failure: { type: "BadSignature", message: "the webhook signature does not match" } };
  }
  let value: unknown;
  try {
    value = JSON.parse(body);
  } catch {
    return { failure: { type: "NotAnUpdate", message: "the webhook body is not JSON" } };
  }
  if (!isTrackingUpdate(value)) {
    return { failure: { type: "NotAnUpdate", message: "the webhook body is not a tracking update" } };
  }
  return { data: value };
}

function isTrackingUpdate(value: unknown): value is TrackingUpdate {
  return (
    typeof value === "object" &&
    value !== null &&
    "parcelId" in value &&
    typeof value.parcelId === "string" &&
    "milestone" in value &&
    typeof value.milestone === "string" &&
    milestones.includes(value.milestone)
  );
}

/** Sends each update to the customer, and resolves once every one is sent. */
export async function notifyAll(updates: readonly TrackingUpdate[], notifier: INotifier): Promise<void> {
  updates.forEach(async (update) => {
    await notifier.send(update);
  });
}
