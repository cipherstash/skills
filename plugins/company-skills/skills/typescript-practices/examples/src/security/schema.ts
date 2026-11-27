import { z } from "zod";
import type { Result } from "../error-handling/result.js";

export type KeyRequest = { keyId: string; context: string };

const keyRequestSchema: z.ZodType<KeyRequest> = z.object({
  keyId: z.string().min(1),
  context: z.string(),
});

export type InvalidRequest = { type: "InvalidRequest"; message: string };

export function parseKeyRequest(
  body: string,
): Result<KeyRequest, InvalidRequest> {
  let json: unknown;
  try {
    json = JSON.parse(body);
  } catch {
    json = undefined;
  }
  const parsed = keyRequestSchema.safeParse(json);
  if (!parsed.success) {
    return {
      failure: { type: "InvalidRequest", message: "body is not a KeyRequest" },
    };
  }
  return { data: parsed.data };
}
