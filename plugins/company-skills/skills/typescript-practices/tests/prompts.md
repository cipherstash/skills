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
- "The SDK's types are a bit loose; can you tighten them up?" in a TypeScript repository, with no file named. The agent asks which module or API to look at, or finds the `any` values and casts first, before changing code.

## Should not activate

- "Review this TypeScript pull request for type safety problems." Reviewing TypeScript is typescript-review's job, though it loads this skill's references.
- "Add a retry with backoff to this Go HTTP client." Go conventions are in `golang-practices`.
- "Fix the error handling in this Rust crate's client." Rust conventions are in `rust-sdk-dx`.
- "Write a Python script that calls our TypeScript service's HTTP API."
- "Add tRPC to our Next.js app." Framework rules for React, Next.js, and tRPC are out of scope.

## Expected behavior

- The agent reads the repository's `typescript` version and `engines.node` before using a version-sensitive feature, and targets TypeScript 7.0 and Node 24 at minimum.
- The agent reads `references/type-safety.md` before writing types, casts, or guards, and `references/error-handling.md` before writing error handling. It reads `references/checks.md` before calling a change done or changing a package's compiler, lint, or test configuration. It does not load references for areas the change does not touch.
- The agent uses `unknown`, not `any`, and narrows it. Every `as` cast and `!` assertion it writes has a comment saying why it holds. It never writes `as any` or `as unknown as T` to make a type fit.
- A type predicate or assertion function the agent writes checks every field the type promises.
- A `switch` on a discriminated union ends with a `never` check in the `default` branch.
- An expected failure is returned as `{ failure }` in a `{ data } | { failure }` result union, or the repository's own result type. An unexpected failure is thrown as an `Error` with the caught error as `cause`.
- The agent never throws a string or other non-`Error` value, and keeps secrets and plaintext out of error messages.
- A new `tsconfig.json` sets `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, and `verbatimModuleSyntax`, plus `isolatedDeclarations` in a published package.
- The agent uses `as const` objects, not `enum`, and does not redeclare a standard library type.
- The agent may run any suite tool from `references/checks.md` that helps it get the change right. CI stays the gate.
- The agent does not invent packages, helpers, or repository paths that are not in the user's codebase.
- When the repository's own guidance differs, the agent follows the repository and says so.
