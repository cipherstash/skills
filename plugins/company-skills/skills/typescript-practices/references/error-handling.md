# Error handling

How to report a failure: a result union for a failure the caller expects, and a thrown `Error` with `cause` for one it does not. The examples target TypeScript 7.0 and Node 24, with the compiler settings that [checks.md](checks.md) requires. They are quoted from the [examples package](../examples/package.json), where CI type-checks, lints, and tests them.

## Expected or unexpected

- A failure is **expected** when a correct program meets it in normal use, and the caller can do something about it: input that does not parse, a record that does not exist, a permission the user lacks. Return it as a value, in a result union.
- A failure is **unexpected** when the caller cannot recover where it is called: a file the program ships with is missing, a dependency breaks its contract, an invariant does not hold. Throw an `Error`.
- Decide once for each function, and say which in its documentation comment. A function that returns a result union does not also throw for an expected failure.

## The result union

Return `{ data }` on success and `{ failure }` on an expected failure. This is the shape CipherStash's TypeScript SDK uses. The `?: never` on the other field lets a caller test `result.failure` and then use `result.data` with no cast. From [`src/error-handling/result.ts`](../examples/src/error-handling/result.ts):

```ts
export type Result<T, E> =
  | { data: T; failure?: never }
  | { data?: never; failure: E };
```

Give each failure a `type` from a fixed set of string literals, so a caller can switch on it, and a `message` a person can read. From [`src/error-handling/result.ts`](../examples/src/error-handling/result.ts):

```ts
export function parsePort(input: string): Result<number, PortFailure> {
  const port = Number(input);
  if (!Number.isInteger(port)) {
    return {
      failure: {
        type: "NotANumber",
        message: `port "${input}" is not a number`,
      },
    };
  }
  if (port < 1 || port > 65535) {
    return {
      failure: {
        type: "OutOfRange",
        message: `port ${port} is not 1 to 65535`,
      },
    };
  }
  return { data: port };
}
```

- Handle a failure where it can be handled, or return it to the caller. Do not throw it.
- A caller that switches on `failure.type` assigns the value to `never` in the `default` branch, as [type-safety.md](type-safety.md) shows, so a new failure type stops the build until it is handled.
- If the repository already has its own result type, use it instead.

## Throwing

- Throw only `Error` or a subclass of it. Never throw a string, an object literal, or any other value: it has no stack trace, and a caller's `instanceof Error` check misses it. oxlint's `only-throw-error` rule reports it.
- When you catch an error and throw a new one, pass the caught error as `cause`. The new message says what this code was doing. The cause keeps what went wrong underneath, with its stack and its `code`.
- Leave out of the message what the cause already says.

From [`src/error-handling/cause.ts`](../examples/src/error-handling/cause.ts):

```ts
export async function readConfig(path: string): Promise<string> {
  try {
    return await readFile(path, "utf8");
  } catch (error) {
    throw new Error(`reading config ${path}`, { cause: error });
  }
}
```

- `return await` inside `try` keeps a rejected promise in the `catch`. A bare `return` would let it pass the `catch` unwrapped.
- Subclass `Error` only when a caller needs `instanceof` to tell the error apart. Set `name` in the subclass, and pass `{ cause }` through to `super`.

## Catching

- A caught value has type `unknown` under `strict`. Narrow it, for example with `instanceof Error`, before reading a property.
- Catch only where you can handle the error, add context, or turn it into a result. Never catch and ignore an error without a comment saying why it cannot matter.
- Handle an error once: return or throw it, or log it and carry on, not both.
- Keep secrets, keys, and plaintext out of error messages and causes. An error message often ends up in a log.
