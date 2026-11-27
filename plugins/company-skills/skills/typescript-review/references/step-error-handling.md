# Step: error handling

Area 1, high priority. Read this, and typescript-practices' `references/error-handling.md`, before reviewing the change's error handling. The practices reference holds the rules and working examples. This file says what to look for in a change, what evidence shows it, and what is not a finding.

## Contents

- [Thrown values that are not errors](#thrown-values-that-are-not-errors)
- [Swallowed errors](#swallowed-errors)
- [Expected failures thrown instead of returned](#expected-failures-thrown-instead-of-returned)
- [Other error-handling defects](#other-error-handling-defects)
- [Evidence](#evidence)
- [Version-sensitive rules](#version-sensitive-rules)
- [Not a finding](#not-a-finding)

## Thrown values that are not errors

Look in every changed line for a `throw` whose value is not an `Error` or a subclass: a string or template literal, a number, an object literal, `null`, or a value of type `unknown` or `any` that the code built itself. Look also for `Promise.reject(<non-Error>)`, and a rejection callback called with one.

Follow where the value goes. A string has no stack trace, so whoever logs it cannot tell where it came from. A caller's `error instanceof Error` check misses it, so a branch that reads `error.message` takes its fallback, and the reason is lost. Name the caller and the line where that happens. With no caller in the repository, the rule alone makes it `minor`. With a caller that loses the reason or mishandles the failure, it is `major`.

## Swallowed errors

Look for an error the change catches and then loses:

- An empty `catch {}` or `catch (error) {}`, or one with only a comment that does not say why the error cannot matter.
- A `catch` that returns a default, `undefined`, `null`, `false`, or an empty value, so the caller cannot tell a failure from a real result.
- `.catch(() => {})` or `.catch(() => undefined)` on a promise, and a promise whose rejection nobody handles because it is not awaited or returned.
- A `catch` that logs the error and then carries on as if the call succeeded, where later code uses state the failed call should have set.
- A `finally` that returns or throws, which discards the error from the `try`.
- A rethrow that drops the caught error: `throw new Error("…")` inside a `catch` with no `{ cause: error }`, where the caught error said what went wrong.

For each one, follow what the code does next when the call fails. The trigger is the call failing, with an example cause. The consequence is what the code does with bad or missing state: reports success, writes a partial file, shows a wrong total. If the change removed a check or a test that the base had, say so: it is part of the cause.

## Expected failures thrown instead of returned

typescript-practices returns an expected failure as `{ failure }` in a `{ data } | { failure }` result union, and throws only for an unexpected one. A failure is expected when a correct program meets it in normal use and the caller can act on it: input that does not parse, a record that does not exist, a permission the user lacks.

Look for a changed function that throws for such a failure. Signs are a doc comment that calls the failure expected or normal, input from a user or a file, and a sibling function in the same module that returns a result union for the same kind of failure. Also look for a function that returns a result union and also throws for an expected failure, so a caller must handle both. The repository's own result type counts as a result union.

The consequence is a caller that does not expect the throw: an uncaught exception that ends a request or a process, or a `catch` far away that cannot tell which failure it caught. Cite the practices rule when no caller shows the consequence.

## Other error-handling defects

The practices reference also covers these. Report them when the change introduces them:

- A caught value read as an `Error` without narrowing, such as `error.message` under a setting where the caught value is `any`.
- An error handled twice: logged and then rethrown or returned, so one failure is reported twice.
- A secret, key, token, or plaintext placed in an error message or its `cause`.
- `return` instead of `return await` inside a `try`, so a rejected promise skips the `catch` that was meant to wrap it.

## Evidence

Most findings in this area come from reading the change, so quote the line and the code path that shows the consequence. oxlint's type-aware `only-throw-error` rule reports a thrown non-`Error` value, but it needs the change's dependencies, so it is usually a limit: quote CI's oxlint result for the head commit instead, when there is one. Biome's `noUselessCatch` reports a `catch` that only rethrows; an empty `catch` is found by reading.

## Version-sensitive rules

Read the version and settings that step 3 recorded before suggesting a fix. `new Error(message, { cause })` needs `lib` to include `es2022` or later. A caught value is `unknown` only under `strict` or `useUnknownInCatchVariables`; otherwise it is `any`, and reading `.message` from it compiles without a check.

## Not a finding

- An empty `catch` with a comment whose reason holds, such as a best-effort cleanup of a temporary file.
- A thrown `Error` subclass from a library the code calls, rethrown unchanged.
- A throw for a failure the caller cannot recover from, such as a broken invariant or a missing file the program ships with. That is what throwing is for.
- Error message style: capitalisation, punctuation, or wording. That belongs to the naming and style area.
- Error handling in code the change neither adds nor makes reachable.
