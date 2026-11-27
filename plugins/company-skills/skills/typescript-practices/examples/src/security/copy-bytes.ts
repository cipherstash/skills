export function encrypt(
  plaintext: Uint8Array,
  native: (bytes: Uint8Array) => Promise<Uint8Array>,
): Promise<Uint8Array> {
  // slice() copies into a new buffer that holds only these bytes, so the
  // caller can change plaintext while the native call runs.
  return native(plaintext.slice());
}
