---
name: typescript-practices
description: Applies CipherStash conventions for writing TypeScript, and the JavaScript files in a TypeScript repository — type safety, error handling, the required compiler settings, and the TypeScript check suite. Use when writing or changing TypeScript or JavaScript code (.ts, .tsx, .mts, .cts, .js, .mjs, .cjs files, their tests, tsconfig.json, or a package's lint and test configuration), such as adding a type, a type guard, a branded ID, a result union, an error, or a new package. Does not apply to other languages, or to reviewing a TypeScript change, which typescript-review does using this skill's references.
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

## References

Read the reference for each area the change touches. Each one states the TypeScript and Node versions its examples target. Its examples are quoted from the [examples package](examples/package.json), where CI type-checks, lints, and tests them.

| Read | When the change involves |
| --- | --- |
| [references/type-safety.md](references/type-safety.md) | `any` and `unknown`, casts and non-null assertions, type guards and assertion functions, branded types, discriminated unions and exhaustive checks, `satisfies`, enums, generic, conditional, and mapped types |
| [references/error-handling.md](references/error-handling.md) | Returning or handling an expected failure, the result union, throwing, wrapping, or catching errors, `cause`, `Error` subclasses |
| [references/checks.md](references/checks.md) | The checks CI runs on every pull request: `tsc`, Biome, oxlint, Vitest with coverage, osv-scanner, semgrep, publint and attw, property tests for code that parses untrusted input, their pinned versions, and the files that run code during a check |

The templates in `assets/` are [tsconfig.json](assets/tsconfig.json), [biome.json](assets/biome.json), and [oxlintrc.json](assets/oxlintrc.json), for oxlint. Save the oxlint copy as `.oxlintrc.json` at the package or repository root: oxlint finds that name by itself, but not `oxlintrc.json`, and without it the type-aware rules are off.
