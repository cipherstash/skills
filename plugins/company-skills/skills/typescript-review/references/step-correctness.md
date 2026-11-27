# Step: correctness and edge cases

Area 2, high priority. Read this, and typescript-practices' `references/type-safety.md` and `references/error-handling.md`, before checking what the change's functions do. typescript-practices has no reference for correctness as such: those two hold the traps that most often make a function do something other than what it says, such as an index read that can be `undefined` or a `switch` that misses a member. This file says what to look for, what evidence shows it, and what is not a finding.

## Contents

- [Check each function against its contract](#check-each-function-against-its-contract)
- [Edge cases to try](#edge-cases-to-try)
- [Evidence](#evidence)
- [Version-sensitive rules](#version-sensitive-rules)
- [Not a finding](#not-a-finding)

## Check each function against its contract

For every function, method, or class the change adds or alters, write down its contract: the documentation comment, the name, the types, and what its callers in the repository rely on. Then read the body against it, one input class at a time. Report a mismatch: an input for which the function does something other than what the contract says.

When the change alters a function's behaviour, read its callers too. A caller that relied on the old behaviour, such as a `{ failure }` for bad input or a sorted result, is a consequence of the change.

## Edge cases to try

Try each of these against every changed function where it can arise:

- **Empty and missing**: an empty array, string, `Map`, or object; `undefined` and `null`; an optional field left out. Under `exactOptionalPropertyTypes`, a field that is left out and a field set to `undefined` are different cases: check that the code handles the one its callers send.
- **Arithmetic**: division by a value that can be zero, which gives `Infinity` or `NaN` with no error, and `NaN` spreading through later sums and comparisons, where every comparison with it is false. Integers above `Number.MAX_SAFE_INTEGER`, such as a 64-bit ID or an amount in minor units, lose precision: use `bigint` or a string. Floating-point money.
- **Indexing**: `items[0]`, `items.at(-1)`, or `items[i]` on an array that can be shorter; a `Map` or object read that assumes the key exists. Under `noUncheckedIndexedAccess` the type says `undefined` is possible, so look at how the code handles it.
- **Truthiness**: `if (value)` or `value || fallback` where `0`, `""`, or `false` is a valid value. `??` keeps them; `||` replaces them.
- **Equality and sorting**: `==` where `===` is meant; objects or arrays compared with `===`, which compares identity; `Array.prototype.sort()` with no compare function, which sorts numbers as strings; `sort` and `reverse` changing the caller's array.
- **Exhaustiveness**: a `switch` or `if` chain over a union that misses a member, with no `never` check in its `default`, so a member added later falls through without a compile error.
- **Text and time**: `length` used as a character count on text outside the Basic Multilingual Plane; `Date` months counted from 0; `new Date(string)` with a format the specification does not define; local time where UTC is meant.
- **Copies and aliasing**: a function that returns or stores the caller's array or object and later changes it, or a shallow copy, `{ ...value }`, where a nested field is then changed.
- **Boundaries**: one element, negative numbers, and off-by-one ranges (`<` against `<=`), and `slice(start, end)` whose `end` is exclusive.

The trigger is the input; the consequence is what the function returns or does then. A `TypeError` in a function that takes input from outside the process is at least `major`.

## Evidence

- Reading: quote the documentation comment or caller that states the contract, and the line that breaks it.
- A failing test in the temporary worktree: to show an edge case, you may add a test there that calls the function with that input, and quote its output. It runs the change's code, so it runs only where `checks.md` allows tests to run. Say that the test was written for the review.
- `tsc --noEmit` under the required compiler settings reports some of these: an index read used as defined, a missing `switch` member when the `default` has a `never` check, and an impossible comparison. It needs the change's dependencies, so it is usually a limit: quote CI's type check for the head commit instead, when there is one.
- An edge case on a branch no test runs is more likely to be wrong; it is not a finding by itself.

## Version-sensitive rules

Read the settings that step 3 recorded. Without `noUncheckedIndexedAccess`, an index read has the element type, so the compiler says nothing about a missing element: report the read. Without `strictNullChecks`, through `strict`, `null` and `undefined` are in every type. A fix that uses `Array.prototype.toSorted` or `Object.groupBy` needs `lib` to include `es2023` or `es2024`.

## Not a finding

- An input the contract excludes, such as an empty array that the documentation comment says must not be empty, unless a caller in the change passes it.
- Behaviour the documentation comment does not promise and no caller relies on.
- A throw for a broken invariant that the function documents.
- A rounding or ordering choice that the documentation comment states.
- An unsafe cast or `any` that lets the wrong case through. That belongs to the type safety area: report it there, once.
