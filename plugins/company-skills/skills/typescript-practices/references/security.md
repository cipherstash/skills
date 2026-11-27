# Security

How to keep untrusted input, secrets, and key material safe: parse at the boundary, block prototype pollution and slow regular expressions, keep secrets out of logs, compare in constant time, and copy bytes before native code reads them. The examples target TypeScript 7.0 and Node 24, with the compiler settings that [checks.md](checks.md) requires. They are quoted from the [examples package](../examples/package.json), where CI type-checks, lints, and tests them.

## Parse untrusted input with a schema at the boundary

Untrusted input is anything from outside the process: a request body, a file, an environment variable, a message, or a response from another service. Its static type is a guess until it is checked. Parse it with a schema where it enters, and pass on only the parsed value. Never cast it, as in `JSON.parse(body) as KeyRequest`. Use the schema library the repository already uses, such as zod. Declare the type, and annotate the schema with it, so the compiler checks that they agree and `isolatedDeclarations` has the type it needs. From [`src/security/schema.ts`](../examples/src/security/schema.ts):

```ts
const KeyRequest: z.ZodType<KeyRequest> = z.object({
  keyId: z.string().min(1),
  context: z.string(),
});
```

Return input that does not parse as an expected failure, as [error-handling.md](error-handling.md) says. From [`src/security/schema.ts`](../examples/src/security/schema.ts):

```ts
export function parseKeyRequest(
  body: string,
): Result<KeyRequest, InvalidRequest> {
  let json: unknown;
  try {
    json = JSON.parse(body);
  } catch {
    json = undefined;
  }
  const parsed = KeyRequest.safeParse(json);
  if (!parsed.success) {
    return {
      failure: { type: "InvalidRequest", message: "body is not a KeyRequest" },
    };
  }
  return { data: parsed.data };
}
```

- The failure message does not repeat the input. The input may hold a secret.
- A parser of untrusted input has a property test, as [testing.md](testing.md) says.

## Prototype pollution

`JSON.parse` keeps a `__proto__` key as an ordinary property. Code that later copies keys one by one into another object, such as a deep merge, `Object.assign`, or `target[key] = value`, calls the `__proto__` setter instead. That changes the object's prototype. A deep merge goes on to write into the prototype itself, which can be `Object.prototype`, shared by every object in the process.

- Parse with a schema. A zod object keeps only the keys it names.
- Never deep-merge untrusted input into an object. Pick the fields you need.
- Store values under keys that come from input in a `Map`, not a plain object.
- Check keys with `Object.hasOwn`, not `in` or `obj[key] !== undefined`, which also see the prototype.

## Regular expressions that can run for a very long time

A regular expression with a repeated group that can match the same text more than one way, such as `(a+)+$` or `(a|aa)*$`, can take time exponential in the input's length when it fails to match. One request can then stop the event loop.

- Do not nest quantifiers or repeat alternatives that overlap in a regular expression that runs on untrusted input.
- Limit the input's length before you match it.
- Prefer a parser, `URL`, or string methods such as `split` and `startsWith` to a complex regular expression.
- Never build a regular expression from input. If you must, escape every special character first.

## Secrets in logs and errors

- Never log, or put in an error's message or `cause`, a key, a token, a password, plaintext, or a whole request or response body.
- Do not log an object that may hold a secret. `console.log` and `JSON.stringify` print every field.
- A class that holds a secret defines `toJSON()` and `[Symbol.for("nodejs.util.inspect.custom")]()` to return a redacted placeholder.
- Make secrets with `crypto.randomBytes` or `crypto.getRandomValues`, and IDs with `crypto.randomUUID`. Never use `Math.random`.
- Never pass input to `eval`, `new Function`, `vm`, or a shell. Run a program with `execFile` and an array of arguments, not `exec`.

## Constant-time comparison

Compare a token, a MAC, or a hash with `crypto.timingSafeEqual`, never `===`, which stops at the first byte that differs and so tells an attacker how much matched. From [`src/security/constant-time.ts`](../examples/src/security/constant-time.ts):

```ts
// Hash both sides first: timingSafeEqual throws on inputs of different
// lengths, and the hashes are always 32 bytes, so no length leaks.
export function tokensMatch(given: string, expected: string): boolean {
  const a = createHash("sha256").update(given).digest();
  const b = createHash("sha256").update(expected).digest();
  return timingSafeEqual(a, b);
}
```

## Copy a `Uint8Array` before passing it to native code

An async native call, such as one through napi-rs, can read its input on another thread after the JavaScript call returns. If the caller changes the array before the promise settles, the native code reads the changed bytes. A `Uint8Array` can also be a view of a larger buffer: Node's `Buffer.from` puts a small `Buffer` in a shared pool, and native code that reads the whole `buffer` sees other data. Pass a copy. From [`src/security/copy-bytes.ts`](../examples/src/security/copy-bytes.ts):

```ts
export function encrypt(
  plaintext: Uint8Array,
  native: (bytes: Uint8Array) => Promise<Uint8Array>,
): Promise<Uint8Array> {
  // slice() copies into a new buffer that holds only these bytes, so the
  // caller can change plaintext while the native call runs.
  return native(plaintext.slice());
}
```

- `subarray()` does not copy. It returns a view of the same buffer.
- Use `Uint8Array`, not `Buffer`, in a public API's types.
- When you are done with a buffer that holds a key or plaintext, overwrite it with `fill(0)`. This is a best effort, because the engine may hold other copies.
