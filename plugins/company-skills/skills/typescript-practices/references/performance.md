# Performance

How to keep TypeScript code and its builds fast. The rules target TypeScript 7.0 and Node 24. Prose states them, with no examples, and no check in the suite measures performance: a benchmark is evidence for a change, not a gate.

## Measure first

- Change code for speed only when a measurement shows it is slow, and measure again after the change. Say in the pull request what you measured, how, and the numbers before and after.
- Profile with `node --cpu-prof`, and open the profile in Chrome DevTools. Measure memory with `node --heap-prof` or a heap snapshot.
- Write a benchmark with `vitest bench` in a `*.bench.ts` file. Run it on the same machine before and after the change. A benchmark is not part of `vitest run`, and CI does not gate on it.
- A clear version that is fast enough beats a fast version that is hard to read.

## The event loop

Node runs JavaScript on one thread. While a function runs, no other request, timer, or callback can run.

- Never use the synchronous file, crypto, or child process APIs, such as `readFileSync`, `pbkdf2Sync`, or `execSync`, in code that serves requests. Use the promise versions. They are fine in a command-line tool or at start-up.
- Move CPU-heavy work, such as hashing a large file or parsing a large document, to a `worker_threads` worker or to native code, so it does not block the loop.
- Bound the size of any input you parse, sort, or match with a regular expression. [security.md](security.md) says why for regular expressions.
- Limit how many network calls, file reads, or native calls run at once, as [async.md](async.md) says. Starting thousands at once uses more memory and is often slower.

## Native calls and bytes

- Crossing from JavaScript into native code, such as a napi-rs addon, has a fixed cost on each call. Prefer one call that handles many items, such as a bulk encrypt or decrypt, to one call per item.
- Copy a buffer once, where [security.md](security.md) requires it before a native call. Do not copy it again on the way through the code. `subarray()` gives a view without a copy where no native call follows.
- Read a large file or response as a stream, not all at once, when the code can handle it piece by piece.
- Keep `Uint8Array` data as bytes. Converting to a string and back, such as to base64 or hex, costs time and memory each way.

## Data structures

- Look up by key in a `Map` or `Set`, not by searching an array. Use a `Map` for keys that come from input, as [security.md](security.md) also says.
- Build a large string from parts with an array and `join`, or a template literal. Do not add to a string one character at a time in a loop over a large input.
- Do not wrap synchronous work in a promise. An `async` function that never awaits still costs a promise for each call.
- Create a regular expression, a schema, or an `Intl` formatter once at module level, not on every call.

## Type-check and build speed

- TypeScript 7 type-checks in parallel. Fix the `--checkers` count in CI, as [checks.md](checks.md) says, so results do not depend on the machine.
- Find what makes a type-check slow with `tsc --extendedDiagnostics`, which prints the time and the number of types for each phase.
- Deeply recursive conditional types, and unions of thousands of members, slow every type-check and editor of the code. Simplify the type, or give it an explicit annotation, when one shows up in the diagnostics.
- Split a large repository into packages with their own `tsconfig`. Under `isolatedDeclarations`, each file's declarations need no type-check of the files it imports, so tools can build them in parallel.
