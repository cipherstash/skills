---
name: typescript-practices
description: Applies CipherStash conventions for writing TypeScript, and the JavaScript files in a TypeScript repository — type safety, error handling, async code, testing, security, dependencies, performance, packages and exports, naming, documentation, the required compiler settings, and the TypeScript check suite. Use when writing or changing TypeScript or JavaScript code (.ts, .tsx, .mts, .cts, .js, .mjs, .cjs files, their tests, tsconfig.json, package.json, pnpm-workspace.yaml, or a package's lint and test configuration), such as adding a type, a type guard, a branded ID, a result union, an error, a promise or AbortSignal, a test or property test, a parser of untrusted input, a dependency, an exports entry, or a new package. Does not apply to other languages, or to reviewing a TypeScript change, which typescript-review does using this skill's references.
user-invocable: false
---

# TypeScript practices

Rules for writing TypeScript, and the JavaScript files in a TypeScript repository. Apply them to every such change, and read the reference for each area the change touches before writing code in it.

## Rules

### General

- The rules target TypeScript 7.0 and Node 24 at minimum. Read the repository's `typescript` version and `engines.node` before using a feature that needs a newer one.
- If the repository's own guidance differs from these rules, follow the repository. Say that you did.
- The TypeScript check suite in [references/checks.md](references/checks.md) lists the checks CI runs on every pull request. Before calling a change done, run any suite tool that helps you get it right. CI is the gate.
- Turn on `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, and `verbatimModuleSyntax` in every `tsconfig`, plus `isolatedDeclarations` in a published package. Start a new package from the templates in `assets/`.
- Format and lint with Biome and oxlint, through the suite.

### Type safety

- Use `unknown`, not `any`, for a value whose type you do not know. Narrow it before use.
- Give every `as` cast and `!` assertion a comment saying why it holds. Never cast through `any` or `unknown` to make a type fit.
- A type predicate or assertion function checks every field of the type it promises.
- Give IDs, keys, and ciphertexts that must not mix a branded type.
- Switch on a discriminated union exhaustively, with a `never` check in the `default` branch.
- Use `satisfies` to check a value against a type without widening it.
- Use `as const` objects, not `enum`. Use the standard library's utility types, and never redeclare one.

### Errors

- Return an expected failure as `{ failure }` in a `{ data } | { failure }` result union. Throw for an unexpected one.
- Throw only `Error` or a subclass. When you rethrow, pass the caught error as `cause`.
- Handle an error once. Keep secrets, keys, and plaintext out of error messages.

### Async code

- Await or return every promise. Never pass an `async` function where the caller ignores what it returns.
- A function that waits on I/O or a timer takes an `AbortSignal` and passes it to every call that accepts one.
- Use `Promise.all` when every result is needed, and `Promise.allSettled` when the pieces of work are independent. Limit how many run at once.

### Testing

- Test behaviour through a module's exports with Vitest, in `<module>.test.ts`. Coverage has no threshold.
- Check an exported generic type, or narrowing a caller relies on, with `expectTypeOf`.
- A function that parses untrusted input has a fast-check property test. Pull request CI runs it with a fixed seed and a set number of runs.

### Security

- Parse untrusted input with a schema where it enters. Never cast it to a type.
- Never copy keys from untrusted input into a plain object one by one, or build a regular expression that can run for a very long time on it.
- Keep keys, tokens, and plaintext out of logs and errors. Compare secrets with `crypto.timingSafeEqual`.
- Copy a `Uint8Array` with `slice()` before passing it to an async native call.

### Dependencies

- Use pnpm, pinned in `packageManager`, with a committed `pnpm-lock.yaml` and `pnpm install --frozen-lockfile` in CI.
- Set `minimumReleaseAge`, `strictDepBuilds`, and `blockExoticSubdeps`. Approve an install script in `allowBuilds` only with a reason.
- Fix every vulnerability osv-scanner reports.

### Performance

- Measure before and after a change made for speed.
- Never block the event loop with synchronous I/O or long CPU work in code that serves requests. Batch native calls.

### Packages, naming, and documentation

- A new package publishes ESM only, with an `exports` map that publint and attw accept. A repository with its own module-format rule keeps it.
- Write type-only imports with `import type` or an inline `type` modifier.
- Name types in `PascalCase`, values in `camelCase`, and files in `kebab-case`. Use named exports.
- Give every export of a published package a documentation comment.

## References

Read the reference for each area the change touches. Each one states the TypeScript and Node versions its examples target. Its examples are quoted from the [examples package](examples/package.json), where CI type-checks, lints, and tests them.

| Read | When the change involves |
| --- | --- |
| [references/type-safety.md](references/type-safety.md) | `any` and `unknown`, casts and non-null assertions, type guards and assertion functions, branded types, discriminated unions and exhaustive checks, `satisfies`, enums, generic, conditional, and mapped types |
| [references/error-handling.md](references/error-handling.md) | Returning or handling an expected failure, the result union, throwing, wrapping, or catching errors, `cause`, `Error` subclasses |
| [references/async.md](references/async.md) | Promises, `await`, un-awaited promises, callbacks that return a promise, `AbortSignal` and cancellation, timeouts, `Promise.all`, `Promise.allSettled`, `Promise.race`, how many calls run at once |
| [references/testing.md](references/testing.md) | Writing or changing a test, Vitest, mocks and fake timers, type tests with `expectTypeOf`, fast-check property tests, the fast-check seed and run count, a parser of untrusted input that needs a test |
| [references/security.md](references/security.md) | Untrusted input and schemas, prototype pollution, regular expressions on input, secrets in logs and errors, randomness, `eval` and shells, comparing tokens or MACs, `Uint8Array` buffers passed to native code |
| [references/dependencies.md](references/dependencies.md) | Adding, removing, or updating a dependency, `package.json` dependency fields, `pnpm-lock.yaml`, `pnpm-workspace.yaml` settings, install scripts, overrides, osv-scanner findings |
| [references/performance.md](references/performance.md) | A change made for speed or memory, benchmarks and profiles, synchronous I/O, CPU-heavy work, batching native calls, slow type-checks |
| [references/project-structure.md](references/project-structure.md) | A new package, `package.json` `type`, `files`, and `exports`, ESM or CommonJS, imports and module resolution, `tsconfig` files and `paths`, `isolatedDeclarations`, publint and attw, names, files, exports, and documentation comments |
| [references/checks.md](references/checks.md) | The checks CI runs on every pull request: `tsc`, Biome, oxlint, Vitest with coverage, osv-scanner, semgrep, publint and attw, property tests for code that parses untrusted input, their pinned versions, and the files that run code during a check |

The templates in `assets/` are [tsconfig.json](assets/tsconfig.json), [biome.json](assets/biome.json), and [oxlintrc.json](assets/oxlintrc.json), for oxlint.
