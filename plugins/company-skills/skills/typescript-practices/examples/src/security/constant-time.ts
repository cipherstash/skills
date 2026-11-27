import { createHash, timingSafeEqual } from "node:crypto";

// Hash both sides first: timingSafeEqual throws on inputs of different
// lengths, and the hashes are always 32 bytes, so no length leaks.
export function tokensMatch(given: string, expected: string): boolean {
  const a = createHash("sha256").update(given).digest();
  const b = createHash("sha256").update(expected).digest();
  return timingSafeEqual(a, b);
}
