# Behavior cases

This is a background convention skill: it is applied while the agent writes TypeScript, or JavaScript in a TypeScript repository, not invoked by name. typescript-review will also load it to read its references during a review.

## Should activate

- "Add a `KeyId` type to the SDK so key IDs can't be passed where a ciphertext is expected." (in a TypeScript package) The agent adds a branded type.
- "`decrypt` throws a string when the key is missing; make it fail properly." (in a TypeScript SDK) The agent throws an `Error`, or returns a `{ failure }` result if the failure is expected, and passes any caught error as `cause`.
- "Parse the `--port` flag in `cli.ts` and tell the user when it's wrong." The agent returns a result union for the bad input instead of throwing.
- "Add a `status` field to `RequestState` for a cancelled request." The agent adds the union member and handles it in every exhaustive `switch`.
- "Write a guard that checks the JSON we get back is a `User`." The guard checks every field, or the agent parses with a schema.
- "Set up `tsconfig.json` for a new package in our monorepo." The agent starts from `assets/tsconfig.json`, with the required compiler settings.
- "Fix the lint errors in `scripts/release.mjs`." (a JavaScript file in a TypeScript repository)
- "Add a test for `parseConfig` in `config.test.ts`."
- "`syncKeys` sometimes finishes before the keys are written; fix it." (in a TypeScript service) The agent awaits or returns every promise, and reads `references/async.md`.
- "Let callers cancel `fetchDataKey` after a timeout." The agent takes an `AbortSignal` and passes it to every call that accepts one.
- "Revoke all of a user's keys, and tell me which ones failed." The agent uses `Promise.allSettled`, not `Promise.all`.
- "Add a handler that reads the JSON body of `POST /keys`." The agent parses the body with a schema at the boundary, returns a bad body as a failure, and adds a fast-check property test that imports the fixed seed and run count from the shared fast-check module.
- "Check the webhook's HMAC signature." The agent compares with `crypto.timingSafeEqual`, not `===`.
- "Pass the plaintext `Uint8Array` to the native `encrypt` binding." The agent passes a copy made with `slice()`.
- "Add `date-fns` to the SDK." The agent uses pnpm, commits the lockfile change, and checks the release-age and install-script settings.
- "Create a new `@cipherstash/keys` package in the monorepo." The agent publishes ESM only, with an `exports` map, `isolatedDeclarations`, and documentation comments on its exports, unless the repository has its own module-format rule.
- "The SDK's types are a bit loose; can you tighten them up?" in a TypeScript repository, with no file named. The agent asks which module or API to look at, or finds the `any` values and casts first, before changing code.

## Should not activate

- "Review this TypeScript pull request for type safety problems." Reviewing TypeScript is typescript-review's job, though it loads this skill's references.
- "Add a retry with backoff to this Go HTTP client." Go conventions are in `golang-practices`.
- "Fix the error handling in this Rust crate's client." Rust conventions are in `rust-sdk-dx`.
- "Write a Python script that calls our TypeScript service's HTTP API."
- "Add tRPC to our Next.js app." Framework rules for React, Next.js, and tRPC are out of scope.

## Expected behavior

- The agent reads the repository's `typescript` version and `engines.node` before using a version-sensitive feature, and targets TypeScript 7.0 and Node 24 at minimum.
- The agent reads `references/type-safety.md` before writing types, casts, or guards, and `references/error-handling.md` before writing error handling. It reads `references/async.md`, `references/testing.md`, `references/security.md`, `references/dependencies.md`, `references/performance.md`, or `references/project-structure.md` when the change touches that area, as the SKILL.md table says. It reads `references/checks.md` before calling a change done or changing a package's compiler, lint, or test configuration. It does not load references for areas the change does not touch.
- The agent uses `unknown`, not `any`, and narrows it. Every `as` cast and `!` assertion it writes has a comment saying why it holds. It never writes `as any` or `as unknown as T` to make a type fit.
- A type predicate or assertion function the agent writes checks every field the type promises.
- A `switch` on a discriminated union ends with a `never` check in the `default` branch.
- An expected failure is returned as `{ failure }` in a `{ data } | { failure }` result union, or the repository's own result type. An unexpected failure is thrown as an `Error` with the caught error as `cause`.
- The agent never throws a string or other non-`Error` value, and keeps secrets and plaintext out of error messages.
- A new `tsconfig.json` sets `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, and `verbatimModuleSyntax`, plus `isolatedDeclarations` in a published package.
- The agent uses `as const` objects, not `enum`, and does not redeclare a standard library type.
- The agent awaits or returns every promise, passes an `AbortSignal` down from any function that waits on I/O, and picks `Promise.all` or `Promise.allSettled` by whether the pieces of work are independent.
- A test the agent writes goes through the module's exports with Vitest. A parser of untrusted input gets a fast-check property test, with the seed and run count set once in a shared module that the test imports.
- The agent parses untrusted input with a schema, never logs a secret, compares secrets in constant time, and copies a `Uint8Array` before an async native call.
- The agent adds dependencies with pnpm, keeps `pnpm-lock.yaml` in step, and approves no install script without a reason.
- A new package publishes ESM only, with `types` first in each `exports` entry. In a repository that publishes both formats, the agent keeps both.
- The agent may run any suite tool from `references/checks.md` that helps it get the change right. CI stays the gate.
- The agent does not invent packages, helpers, or repository paths that are not in the user's codebase.
- When the repository's own guidance differs, the agent follows the repository and says so.
