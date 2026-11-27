import type { Parcel } from "./manifest.js";

/** A parcel the carrier has accepted, with the tracking code the carrier gave it. */
export type TrackedParcel = Parcel & { trackingCode: string };

/**
 * Returns the text printed on a parcel's label: its tracking code and its weight. Parcels are labelled as they are
 * packed, before or after the carrier accepts them.
 */
export function labelText(parcel: Parcel | TrackedParcel): string {
  const tracked = parcel as unknown as TrackedParcel;
  return `${tracked.trackingCode.toUpperCase()} ${parcel.weightGrams} g`;
}
