# Seeded-defect fixture: expected findings

A sample TypeScript change with one planted defect in each of the eleven checklist areas, and the findings a correct review must report. Run it by hand: nothing in CI drives an agent. `tests/test_fixture.py` checks that each location below is exactly the line it quotes, that the base is clean, and that each defect comes from the change.

The fixture holds planted defects, so CI's TypeScript check suite never runs over it. That suite runs over typescript-practices' examples package only.

## Contents

- [The change](#the-change)
- [Run it](#run-it)
- [Checks a correct review reports](#checks-a-correct-review-reports)
- Findings T1 to T11, one per area in the order of SKILL.md's areas table
- [May report](#may-report)
- [Must not report](#must-not-report)

## The change

`base/` is a published TypeScript package, `parcel-manifest` at version `0.4.0`, with TypeScript `7.0.2`, Vitest `5.1.1`, an ESM-only `exports` map, and the compiler settings typescript-practices requires, `isolatedDeclarations` among them. Its entry point, `src/index.ts`, exports `src/manifest.ts`, whose `parseManifest` reads the text of a manifest file that a customer uploads and returns each expected failure as `{ failure }`. `head/` is the same package after a change titled "manifest: weights, labels, and carrier tracking updates". It:

- replaces `totalWeightGrams` with `totalWeight`, which takes a unit, and adds `meanWeightGrams`, `weightOf`, and `weightLine` to `src/manifest.ts`, with tests for non-empty manifests and a parcel that is in the manifest;
- adds `src/labels.ts` (`TrackedParcel`, `labelText`, `packingWeight`) and tests for a tracked parcel;
- adds `src/tracking.ts` (`parseTrackingUpdate`, which reads a carrier's signed webhook body, `notifyAll`, and the `INotifier` interface) and tests with fixed inputs;
- exports both new modules from `src/index.ts`;
- adds `@vitest/coverage-v8` to `devDependencies`.

The change touches no file on the execution surface: no Vitest or Vite configuration, no oxlint configuration, no build configuration, and no `package.json` script. Its `tsconfig.json` and `tsconfig.build.json` are the same as the base's.

The finding IDs below are labels for this file. A report numbers its findings most severe first, so its IDs can differ.

## Run it

Build a repository with the change as its last commit, in a scratch directory:

```sh
fixture=<typescript-review skill dir>/tests/fixtures/seeded-change
work=$(mktemp -d)
cp -R "$fixture/base/." "$work"
cd "$work"
git init -q && git add -A && git commit -qm "manifest: parse uploaded manifests"
cp -R "$fixture/head/." "$work"
git add -A && git commit -qm "manifest: weights, labels, and carrier tracking updates"
```

Then, in a session started in `$work`, ask for a review of the last commit, for example "Review my last commit for TypeScript problems." The user wrote the commit, but the review still asks before it runs the tests, and it installs no dependencies.

## Checks a correct review reports

- The TypeScript version, read from `package.json`, is `7.0.2`, and `engines.node` is `>=24`. The `tsconfig.json` settings read are `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `verbatimModuleSyntax`, and `isolatedDeclarations`, all on.
- `tsc --noEmit` and `oxlint --type-aware` are not run: they need the package's dependencies, which the review never installs. This is a limit. With the dependencies installed and typescript-practices' `assets/oxlintrc.json`, `tsc` passes at the base and the head, and `oxlint --type-aware` reports nothing at the base and two errors at the head: `typescript(only-throw-error)` at `src/manifest.ts:72` (T1) and `typescript(no-misused-promises)` at `src/tracking.ts:66` (T5).
- Biome and oxlint without type information are not run: the base commit has no configuration for either.
- The tests are not run: they need the package's dependencies, and Vitest runs the change's code. The report gives the exact command, `vitest run --coverage --coverage.provider=v8`. With the dependencies installed, all thirteen tests pass at the head, so they show none of the defects.
- The declaration comparison, publint, and attw are not run: they need the dependencies, and publint and attw need a build. The review compares the exports by reading, under `isolatedDeclarations`, and its API changes section lists `totalWeightGrams` as removed. With the dependencies installed and the package built, publint and attw pass at both the base and the head: the package's shape is fine, and the removal shows only in the declaration comparison.
- osv-scanner and semgrep are not run unless the user allows the network. The package has no lockfile.
- The repository has no CI, so there is no CI result to quote for the head commit.
- The typescript-practices references read for each area, as SKILL.md's areas table names them, and the step reference for each area. If the skill could not be loaded, the review says so as a limit instead.

The check suite section lists the missing checks:

- The repository has no CI. The check suite section lists seven checks as missing, one line each: the Type check (`tsc --noEmit`), Format and general lint (`biome ci`), Type-aware lint (`oxlint --type-aware`), Tests and coverage (`vitest run --coverage`), Vulnerabilities (osv-scanner), SAST (semgrep), and Package shape (publint and attw, since the package is not private). None of them is a finding. The property test rule is not a missing line: CI cannot tell that a property test is missing, so the review enforces it, as T4 does.

The verdict is `REQUEST_CHANGES`: T1, T2, T3, T5, and T7 are major.

## T1 · major · error handling

- Location: `head/src/manifest.ts:72`
- Line: ``throw `no parcel with id ${id} in the manifest`;``
- Cause: `weightOf` throws a string. Its doc comment calls an unknown id an expected failure, but the change throws it instead of returning it in a result union, as `parseManifest` in the same file does.
- Trigger and consequence: a customer asks for an id that is not in the manifest, such as `P-9`. `weightLine` catches the string, and its `error instanceof Error` check is false, so the tracking page shows `P-9: something went wrong` and the reason is lost. A string has no stack trace, so a caller that logs it cannot tell where it came from.
- Rule: typescript-practices, error handling: throw only `Error` or a subclass; return an expected failure as `{ failure }` in a result union.
- Evidence: reading the function and its caller `weightLine` at `src/manifest.ts:78`. With the dependencies installed, `oxlint --type-aware` reports `typescript(only-throw-error)` at this line. No test asks for a missing id.
- A correct fix returns `{ failure: { type: "NotFound", message } }` from `weightOf` in a `{ data } | { failure }` result, and has `weightLine` show the failure's message.

## T2 · major · correctness and edge cases

- Location: `head/src/manifest.ts:62`
- Line: `return totalWeight(parcels, "g") / parcels.length;`
- Cause: `meanWeightGrams` is documented to return 0 for an empty manifest, but it divides by `parcels.length` without checking it.
- Trigger and consequence: an empty manifest, `[]`, which `parseManifest` accepts, makes `meanWeightGrams` return `NaN` (`0 / 0`) where the documentation promises 0, with no error. Any later sum or comparison with it is `NaN` or false, and a page that prints it shows `NaN`. Major, not critical: the review shows no caller that stores or sends the value.
- Evidence: reading the function against its doc comment. The one test passes two parcels, so the tests pass.
- A correct fix returns 0 when `parcels.length === 0`, and adds that case to the test.

## T3 · major · type safety

- Location: `head/src/labels.ts:11`
- Line: `const tracked = parcel as unknown as TrackedParcel;`
- Cause: `labelText` takes a `Parcel | TrackedParcel` and casts it through `unknown` to `TrackedParcel`, so the compiler no longer sees the case where the parcel has no tracking code. Its doc comment says parcels are labelled before the carrier accepts them, which is that case.
- Trigger and consequence: a parcel with no `trackingCode`, such as one `parseManifest` returns, makes `labelText` throw `TypeError: Cannot read properties of undefined (reading 'toUpperCase')`, and no label prints. Major, not critical: the review shows no caller where an untracked parcel is the common path.
- Rule: typescript-practices, type safety: never cast through `any` or `unknown` to make a type fit; give every `as` cast a comment saying why it holds.
- Evidence: reading the function and its doc comment. `tsc` and `oxlint --type-aware` report nothing here. The one test passes a tracked parcel.
- A correct fix narrows with `"trackingCode" in parcel` and handles the untracked case, or takes only a `TrackedParcel`.

## T4 · minor · testing and coverage

- Location: `head/src/tracking.ts:35`
- Line: `export function parseTrackingUpdate(body: string, signatureHex: string, sharedKey: string): TrackingResult {`
- Cause: the change adds `parseTrackingUpdate` with no fast-check property test. It reads the body of a carrier's webhook request, which comes from outside the process: untrusted input.
- Rule: typescript-practices, the TypeScript check suite and testing: a function that parses untrusted input must have a fast-check property test, written with `@fast-check/vitest`. CI cannot tell that one is missing, so the review reports it.
- Evidence: reading the function and its doc comment. No file in the package imports `fast-check` or calls `test.prop`. `src/tracking.test.ts` covers it with three fixed bodies only.
- A correct fix adds `@fast-check/vitest` and `fast-check` at the pinned versions, a module that sets the seed and run count, and a property test that `parseTrackingUpdate` returns data or a failure for any body and signature, and never throws.

## T5 · major · async and concurrency

- Location: `head/src/tracking.ts:66`
- Line: `updates.forEach(async (update) => {`
- Cause: `notifyAll` passes an `async` callback to `forEach`, which ignores the promise each call returns, so nothing awaits the sends.
- Trigger and consequence: `notifyAll` resolves before any send has finished, though its doc comment says it resolves once every one is sent, so a caller that marks the updates as delivered does so too early. When a send rejects, such as the email service refusing a message, nothing handles the rejection: Node treats it as an unhandled rejection, which ends the process by default, and the caller never sees the error. Major, not critical: the review shows no caller where a failed send is the common path.
- Rule: typescript-practices, async code: await or return every promise; never pass an `async` function where the caller ignores what it returns.
- Evidence: reading the function. With the dependencies installed, `oxlint --type-aware` reports `typescript(no-misused-promises)` at this line. The one test passes, because its `send` records the update before its first `await`.
- A correct fix awaits the sends, with a `for...of` loop and `await`, or `await Promise.all(updates.map((update) => notifier.send(update)))`.

## T6 · minor · naming and style

- Location: `head/src/tracking.ts:24`
- Line: `export interface INotifier {`
- Cause: the new interface's name has an `I` prefix.
- Rule: typescript-practices, naming and style: do not prefix an interface with `I`.
- Evidence: reading the declaration. It is the only name in the change with the prefix.
- A correct fix renames it `Notifier`.

## T7 · major · security

- Location: `head/src/tracking.ts:37`
- Line: `if (signatureHex !== expected) {`
- Cause: `parseTrackingUpdate` compares the webhook's signature with the HMAC it computes using `!==`, which stops at the first character that differs.
- Trigger and consequence: anyone who can send a request to the webhook can time how long each guess takes to fail and recover a valid signature for a body of their own, a character at a time, then send a forged tracking update that the code accepts. `step-security.md` makes a secret compared with `!==` against a value the caller sends `major`: the review cannot show that the many timed requests are practical.
- Rule: typescript-practices, security: compare a token, a MAC, or a hash with `crypto.timingSafeEqual`, never `===`.
- Evidence: reading the function and its doc comment, which says the carrier sends the signature in a request header. No file in the package calls `timingSafeEqual`.
- A correct fix decodes both hex strings to buffers, checks that their lengths match, and compares them with `timingSafeEqual`.

## T8 · minor · performance

- Location: `head/src/labels.ts:20`
- Line: `const kilograms = new Intl.NumberFormat("en-AU", { maximumFractionDigits: 2 });`
- Cause: `packingWeight` builds a new `Intl.NumberFormat` on every call. Its doc comment says the packing sheet calls it for every parcel in a manifest.
- Rule: typescript-practices, performance: create a regular expression, a schema, or an `Intl` formatter once at module level, not on every call.
- Evidence: reading the function and its doc comment. No benchmark was run.
- A correct fix moves the formatter to a module-level constant.

## T9 · minor · dependency management

- Location: `head/package.json:23`
- Line: `"@vitest/coverage-v8": "^5.1.1",`
- Cause: the change adds `@vitest/coverage-v8`, a tool of the TypeScript check suite, with a caret range, though every other tool in the package is pinned exactly and `vitest` is pinned at `5.1.1`.
- Trigger and consequence: the package has no lockfile, so each install takes the newest `5.x`. On 2026-11-27 a fresh install resolved `@vitest/coverage-v8` `5.1.2` beside `vitest` `5.1.1`, so the coverage provider and the test runner it plugs into come from different releases, and the coverage CI reports can change with no change to the repository.
- Rule: typescript-practices, dependencies and the check suite: pin each tool at an exact version; a caret or tilde range is not pinned.
- Evidence: reading `package.json` at the base and the head.
- A correct fix pins `"@vitest/coverage-v8": "5.1.1"`, the version typescript-practices pins with `vitest`.

## T10 · minor · documentation

- Location: `head/src/manifest.ts:55`
- Line: `export function totalWeight(parcels: readonly Parcel[], unit: "g" | "kg"): number {`
- Cause: the change exports `totalWeight` from the published package's entry point with no documentation comment. The comment on `totalWeightGrams`, which it replaces, went with the old function, so nothing tells a caller that the kilogram result is not rounded.
- Rule: typescript-practices, documentation: give every export of a published package a `/** */` documentation comment.
- Evidence: reading the declaration. It is the only export in the change without a documentation comment.
- A correct fix adds a comment such as `/** Returns the total weight of the parcels in the unit asked for, not rounded. */`.

## T11 · minor · breaking changes

- Location: `base/src/manifest.ts:56` (deleted)
- Line: `export function totalWeightGrams(parcels: Parcel[]): number {`
- Cause: the change removes `totalWeightGrams`, which the package's entry point exports, and adds `totalWeight` in its place.
- Trigger and consequence: any user who updates to this version and calls `totalWeightGrams` stops compiling, and plain JavaScript callers get `TypeError: totalWeightGrams is not a function`. The package is at `0.4.0`, below `1.0.0`, so a caret range does not cross a minor version: minor. At `1.0.0` or later, the change would need a major version, and would be major.
- Evidence: the exports of `src/index.ts` and `src/manifest.ts` read at the base and the head. With the dependencies installed, the declaration comparison shows `export declare function totalWeightGrams(parcels: Parcel[]): number;` only at the base. publint and attw pass at both.
- A correct fix keeps `totalWeightGrams`, as a call to `totalWeight(parcels, "g")` marked `@deprecated`, or bumps the version to `0.5.0` and names the removal in the release notes.

## May report

These neither count for nor against the review. For example:

- Testing: no test covers a missing id in `weightOf`, an untracked parcel in `labelText`, an empty manifest in `meanWeightGrams`, or a failed send in `notifyAll`. This may be folded into T1, T2, T3, and T5.
- Error handling: `weightLine` catches every error and shows a fixed text for any value that is not an `Error`.
- Async and concurrency: `notifyAll` takes no `AbortSignal`, though its sends do I/O. The `INotifier` interface gives it no signal to pass on.
- Async and concurrency: `notifyAll` is `async` but awaits nothing. This may be folded into T5.
- Dependency management: the package has no `pnpm-lock.yaml` and no `packageManager`. Both are already missing at the base, so neither is caused by the change.

## Must not report

Each of these would be a false finding.

- `const items: unknown[] = value;` in `parseManifest`. `Array.isArray` narrows `unknown` to `any[]`, and assigning that to `unknown[]` turns the checks back on. It is in the base, not the change.
- The catch in `parseManifest`, which narrows the caught value with `instanceof Error` before reading `message`. It is in the base.
- The `catch` in `parseTrackingUpdate` that returns `{ failure }` for a body that is not JSON. That is an expected failure returned as a result union, as typescript-practices says, not a swallowed error.
- `isTrackingUpdate` as an incomplete type guard. It checks both fields of `TrackingUpdate`, and checks `milestone` against the list of milestones.
- A missing property test for `parseManifest`. It is in the base, and the change does not alter it.
- `totalWeight` dividing by 1000 for kilograms. It divides by a constant, and returns a fraction of a kilogram by design.
- Package shape: publint and attw pass, and the `exports` map is the same at the base and the head.
- A missing changeset or version bump as its own finding. It is part of T11.
- Anything in `base/` that the change does not touch.
