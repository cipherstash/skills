/** One parcel in a shipping manifest. */
export type Parcel = {
  id: string;
  weightGrams: number;
};

/** Why a manifest's text could not be read as a list of parcels. */
export type ManifestFailure = {
  type: "NotJson" | "NotAParcelList";
  message: string;
};

/** A parsed manifest, or the expected failure that stopped it. */
export type ManifestResult =
  | { data: Parcel[]; failure?: never }
  | { data?: never; failure: ManifestFailure };

/**
 * Parses the text of a manifest file that a customer uploads. Text that is not a list of parcels is an expected
 * failure, returned as `{ failure }`.
 */
export function parseManifest(text: string): ManifestResult {
  let value: unknown;
  try {
    value = JSON.parse(text);
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error);
    return { failure: { type: "NotJson", message: `manifest is not JSON: ${reason}` } };
  }
  if (!Array.isArray(value)) {
    return { failure: { type: "NotAParcelList", message: "manifest is not a list" } };
  }
  const items: unknown[] = value;
  const parcels: Parcel[] = [];
  for (const item of items) {
    if (!isParcel(item)) {
      return { failure: { type: "NotAParcelList", message: "manifest holds an entry that is not a parcel" } };
    }
    parcels.push(item);
  }
  return { data: parcels };
}

function isParcel(value: unknown): value is Parcel {
  return (
    typeof value === "object" &&
    value !== null &&
    "id" in value &&
    typeof value.id === "string" &&
    "weightGrams" in value &&
    typeof value.weightGrams === "number"
  );
}

/** Returns the total weight of the parcels, in grams. */
export function totalWeightGrams(parcels: Parcel[]): number {
  return parcels.reduce((sum, parcel) => sum + parcel.weightGrams, 0);
}

/**
 * Returns the weight of the parcel with this id, in grams. A customer asks for a parcel by the id they typed, so an
 * id that is not in the manifest is an expected failure.
 */
export function weightOf(parcels: Parcel[], id: string): number {
  const parcel = parcels.find((candidate) => candidate.id === id);
  if (parcel === undefined) {
    throw `no parcel with id ${id} in the manifest`;
  }
  return parcel.weightGrams;
}

/** Returns the line the tracking page shows for the parcel with this id. */
export function weightLine(parcels: Parcel[], id: string): string {
  try {
    return `${id}: ${weightOf(parcels, id)} g`;
  } catch (error) {
    return `${id}: ${error instanceof Error ? error.message : "something went wrong"}`;
  }
}
