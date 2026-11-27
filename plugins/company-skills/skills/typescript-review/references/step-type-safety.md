# Step: type safety

Area 3, high priority. Read this, and typescript-practices' `references/type-safety.md`, before reviewing the change's types. The practices reference holds the rules and working examples. This file says what to look for in a change, what evidence shows it, and what is not a finding.

An `any`, a cast, or a non-null assertion is a claim the compiler cannot check. Report one when it can hide a real case: a value it lets through that the code then mishandles. Name that case, not only the syntax.

## Contents

- [`any`](#any)
- [Casts](#casts)
- [Non-null assertions](#non-null-assertions)
- [Type guards and assertion functions](#type-guards-and-assertion-functions)
- [Evidence](#evidence)
- [Version-sensitive rules](#version-sensitive-rules)
- [Not a finding](#not-a-finding)

## `any`

Look in every changed line for:

- An explicit `any`: an annotation, a type argument such as `Promise<any>` or `Record<string, any>`, a parameter, or a field in a union of message shapes.
- An implicit `any` that the change lets spread: the result of `JSON.parse`, `response.json()`, or a library call typed `any`, assigned to a typed variable or returned as a typed value without a check.
- An `any` that reaches a property read, a call, or a return, where `unknown` and a narrowing check would have caught the wrong shape.

Follow the value to its first use. The trigger is a value of another shape, such as a field missing from a response. The consequence is the failure at the use: a `TypeError`, `undefined` written into stored data, or a wrong branch taken. An explicit `any` with no traced consequence breaks the practices rule, which makes it `minor`.

## Casts

Look for each `as` cast the change adds, and give most attention to these:

- A double cast through `unknown` or `any`, such as `as unknown as T` or `as any as T`. The compiler accepts it for any two types, so it hides whatever case made the direct cast fail.
- A cast to a narrower type than the value has, such as from a union to one member, or from a base type to one with more required fields, where the code has not tested which member it holds.
- A cast of parsed or received data, such as `JSON.parse(text) as Config`, where the data comes from outside the process. typescript-practices parses that with a schema at the boundary.
- A cast with no comment saying why it holds.

For each one, name the case the cast hides: the member, the missing field, or the input shape the code does not handle. Then trace what that case does at run time. A cast whose hidden case is reachable, with a concrete trigger, is `major`. One whose case the review cannot show reachable breaks the rule only, which is `minor`.

## Non-null assertions

Look for each `!` non-null assertion the change adds, such as `map.get(key)!`, `items[0]!`, or `element!.value`. Find what makes the value `null` or `undefined`: a key that may be missing, an empty array, an element that may not exist, an optional field. Under `noUncheckedIndexedAccess`, every index read can be `undefined`, so an assertion after one claims the index exists.

An assertion that hides a real case, one the code can reach, is a finding: name the input that makes the value missing, and the `TypeError` or wrong result that follows. An assertion whose value the code has just checked, or that a comment explains with a reason that holds, is not.

## Type guards and assertion functions

A changed type predicate (`value is T`) or assertion function (`asserts value is T`) must check every field the type promises. Compare the checks with the type's declaration. A field the guard does not check is a field the compiler then trusts. Name the field, a value that passes the guard without it, and where the code reads it.

## Evidence

Read the change for each of these: the compiler accepts a cast or an assertion by design, so `tsc` passing is not evidence that one is safe. Biome's `noExplicitAny` reports an explicit `any` when the base commit's configuration turns it on, and Biome runs without the change's dependencies. oxlint's type-aware `no-unsafe-*` rules report an `any` value that reaches an assignment, a call, a property read, or a return, but they need the change's dependencies, so they are usually a limit: quote CI's oxlint result for the head commit instead, when there is one.

To show the hidden case, quote the declaration of the type, the line that casts or asserts, and the input that reaches it. A test written for the review runs the change's code, so it runs only where `checks.md` allows tests to run.

## Version-sensitive rules

Read the settings that step 3 recorded. Without `strict`, or with `strictNullChecks` off, `null` and `undefined` are in every type, so a missing check does not show in the types: review the case from the values, not the types. Without `noUncheckedIndexedAccess`, an index read has the element type, so the code may read a missing element with no `!` at all: report the read, not a missing assertion. A fix that uses `satisfies` needs TypeScript 4.9 or later.

## Not a finding

- A cast or `any` that a comment explains, where the reason holds: a library type that demands it, or a branded type's single constructor function, as typescript-practices shows.
- `as const`, and a cast to a wider type, such as `"a" as string`. Neither hides a case.
- An `any` in a `.d.ts` file that describes an untyped library, unless the change's own code passes that `any` on.
- A non-null assertion on a value the code has just checked, where the compiler cannot carry the check across, such as into a callback.
- Types in code the change neither adds nor makes reachable.
