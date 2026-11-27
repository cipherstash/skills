export async function revokeAll(
  keyIds: readonly string[],
  revoke: (keyId: string) => Promise<void>,
): Promise<string[]> {
  const results = await Promise.allSettled(
    keyIds.map((keyId) => revoke(keyId)),
  );
  return keyIds.filter((_, i) => results[i]?.status === "rejected");
}
