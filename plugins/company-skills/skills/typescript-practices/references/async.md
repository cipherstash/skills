# Async code

How to write code that waits: await every promise, pass an `AbortSignal` down so a caller can cancel, and choose between `Promise.all` and `Promise.allSettled`. The examples target TypeScript 7.0 and Node 24, with the compiler settings that [checks.md](checks.md) requires. They are quoted from the [examples package](../examples/package.json), where CI type-checks, lints, and tests them.

## Await every promise

A promise that nothing awaits is un-awaited. Its rejection is lost or crashes the process with an unhandled rejection, and the code after it runs before its work is done.

- `await` every promise, or `return` it to a caller that does. oxlint's `no-floating-promises` rule reports one that is neither.
- Do not pass an `async` function where a caller expects a function that returns nothing, such as an `Array.prototype.forEach` callback or an event listener. Nothing awaits the promise it returns. oxlint's `no-misused-promises` rule reports it. Use a `for...of` loop with `await`, or map to promises and await them together.
- Start work in the background only when nothing needs its result. Mark it with `void`, give it a `.catch()` that logs the failure, and add a comment saying why nothing waits for it.
- Inside `try`, write `return await`, so a rejection reaches the `catch`. [error-handling.md](error-handling.md) shows it.
- Never mix callbacks and promises in one API. Wrap a callback API once with `util.promisify`, or use the `node:*/promises` modules.

## Cancellation with `AbortSignal`

A function that waits on the network, a timer, a file, or a child process takes an `AbortSignal` and passes it to every call it makes that accepts one: `fetch`, `node:timers/promises`, `node:fs/promises`, streams, and `child_process`. The caller decides when to stop. From [`src/async/cancel.ts`](../examples/src/async/cancel.ts):

```ts
export async function poll(
  check: () => Promise<boolean>,
  intervalMs: number,
  signal: AbortSignal,
): Promise<void> {
  while (!(await check())) {
    await setTimeout(intervalMs, undefined, { signal });
  }
}
```

- The caller makes the signal: `AbortSignal.timeout(ms)` for a deadline, an `AbortController` to cancel by hand, and `AbortSignal.any([a, b])` for whichever comes first.
- When the signal aborts, the waiting call rejects. Node's own APIs reject with an error named `AbortError` whose `cause` is the signal's `reason`. `fetch` rejects with the `reason` itself, which `AbortSignal.timeout` makes a `TimeoutError`. Let the rejection reach the caller. Catch it only to clean up, then rethrow it.
- In a loop of steps that take no signal, call `signal.throwIfAborted()` before each step.
- Remove an `abort` event listener when the work finishes, or pass `{ once: true }`, so a long-lived signal does not keep every listener alive.
- A public function may make the signal optional, as `fetch` does. Under `exactOptionalPropertyTypes`, declare it as `signal?: AbortSignal | undefined` in an options object if callers pass `undefined` through.

## `Promise.all` or `Promise.allSettled`

- Use `Promise.all` when every result is needed and one failure makes the rest useless. It rejects with the first failure. It does not stop the other promises: they keep running, and their results and failures are lost. Pass them one shared signal and abort it when `Promise.all` rejects, so they stop.
- Use `Promise.allSettled` when the pieces of work are independent and each failure must be reported. It waits for every promise and never rejects. Each result has a `status` of `"fulfilled"` with a `value`, or `"rejected"` with a `reason`.

From [`src/async/all-settled.ts`](../examples/src/async/all-settled.ts):

```ts
export async function revokeAll(
  keyIds: readonly string[],
  revoke: (keyId: string) => Promise<void>,
): Promise<string[]> {
  const results = await Promise.allSettled(
    keyIds.map((keyId) => revoke(keyId)),
  );
  return keyIds.filter((_, i) => results[i]?.status === "rejected");
}
```

- Map with an arrow function that passes only the argument you mean. `keyIds.map(revoke)` would also pass the index and the array.
- `Promise.race` settles with the first promise to settle, and `Promise.any` with the first to fulfil. Neither stops the others. To time out a call, pass it `AbortSignal.timeout(ms)` instead of racing it against a timer.

## How much runs at once

- Mapping a long list to promises starts every one at once. For network calls, keys, or files, limit how many run at a time: work through the list in fixed-size batches, or with a small pool of workers that each take the next item.
- Prefer one call that handles many items, such as a bulk encrypt, to many calls that each handle one. [performance.md](performance.md) says why.
- Keep shared state that several async functions change in one place, and change it only between `await`s. Code between two `await`s runs without interruption. Any `await` lets other code change the state.
