import { setImmediate } from "node:timers/promises";
import { expect, test } from "vitest";
import { encrypt } from "./copy-bytes.js";

// Stands in for an async native call that reads its input after a delay.
async function nativeEncrypt(bytes: Uint8Array): Promise<Uint8Array> {
  await setImmediate();
  return bytes;
}

test("the native call sees the bytes as they were when it was called", async () => {
  const plaintext = new Uint8Array([1, 2, 3]);
  const encrypting = encrypt(plaintext, nativeEncrypt);
  plaintext.fill(0);
  expect(await encrypting).toEqual(new Uint8Array([1, 2, 3]));
});

test("the native call gets a buffer that holds only the bytes", async () => {
  const pool = new Uint8Array([9, 1, 2, 9]);
  const sent = await encrypt(pool.subarray(1, 3), nativeEncrypt);
  expect(sent.buffer.byteLength).toBe(2);
});
