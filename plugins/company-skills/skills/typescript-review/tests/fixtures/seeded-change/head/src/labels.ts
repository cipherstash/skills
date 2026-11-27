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

/**
 * Returns a weight in grams as the packing sheet prints it, in kilograms with up to two decimal places, such as
 * `1.25 kg`. The packing sheet calls it once for every parcel in a manifest.
 */
export function packingWeight(grams: number): string {
  const kilograms = new Intl.NumberFormat("en-AU", { maximumFractionDigits: 2 });
  return `${kilograms.format(grams / 1000)} kg`;
}
