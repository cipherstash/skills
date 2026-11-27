export function encrypt(
  plaintext: Uint8Array,
  native: (bytes: Uint8Array) => Promise<Uint8Array>,
): Promise<Uint8Array> {
  // new Uint8Array() copies into a new buffer that holds only these bytes, so
  // the caller can change plaintext while the native call runs. On a Buffer,
  // slice() returns a view, so it does not copy.
  return native(new Uint8Array(plaintext));
}
