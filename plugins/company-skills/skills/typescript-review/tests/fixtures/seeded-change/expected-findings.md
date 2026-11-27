# Seeded-defect fixture: expected findings

A sample TypeScript change with one planted defect for each area this version of `typescript-review` reviews, error handling and type safety, and the findings a correct review must report. Run it by hand: nothing in CI drives an agent. `tests/test_fixture.py` checks that each location below is exactly the line it quotes, that the base is clean, and that each defect comes from the change.

The fixture holds planted defects, so CI's TypeScript check suite never runs over it. That suite runs over typescript-practices' examples package only.

## Contents

- [The change](#the-change)
- [Run it](#run-it)
- [Checks a correct review reports](#checks-a-correct-review-reports)
- Findings T1 and T2, one per area in the order of SKILL.md's areas table
- [May report](#may-report)
- [Must not report](#must-not-report)

## The change

`base/` is a private TypeScript package, with TypeScript `7.0.2`, Vitest `5.1.1`, and the compiler settings typescript-practices requires. Its `parseManifest` reads the text of a manifest file that a customer uploads, and returns each expected failure as `{ failure }`. `head/` is the same package after a change titled "manifest: look up a parcel's weight and print labels". It:

- adds `weightOf` and `weightLine` to `src/manifest.ts`, with a test for a parcel that is in the manifest;
- adds `src/labels.ts` (`TrackedParcel`, `labelText`) and a test for a tracked parcel.

The change touches no file on the execution surface: no Vitest or Vite configuration, no oxlint configuration, and no `package.json` script. Its `package.json` and `tsconfig.json` are the same as the base's.

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
git add -A && git commit -qm "manifest: look up a parcel's weight and print labels"
```

Then, in a session started in `$work`, ask for a review of the last commit, for example "Review my last commit for TypeScript problems." The user wrote the commit, but the review still asks before it runs the tests, and it installs no dependencies.

## Checks a correct review reports

- The TypeScript version, read from `package.json`, is `7.0.2`. The `tsconfig.json` settings read are `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, and `verbatimModuleSyntax`, all on.
- `tsc --noEmit` and `oxlint --type-aware` are not run: they need the package's dependencies, which the review never installs. This is a limit. With the dependencies installed and typescript-practices' `assets/oxlintrc.json`, `tsc` passes at the base and the head, and `oxlint --type-aware` reports `typescript(only-throw-error)` at `src/manifest.ts:67` at the head and nothing at the base.
- Biome and oxlint without type information are not run: the base commit has no configuration for either.
- The tests are not run: they need the package's dependencies, and Vitest runs the change's code. The report gives the exact command, `vitest run`. With the dependencies installed, all seven tests pass at the head, so they show neither defect.
- osv-scanner and semgrep are not run unless the user allows the network. The package has no lockfile.
- The repository has no CI, so there is no CI result to quote for the head commit.
- The typescript-practices references read for each area, as SKILL.md's areas table names them, and the step reference for each area. If the skill could not be loaded, the review says so as a limit instead.
- The nine areas this version has no step for are each listed as not reviewed, with that reason.

The verdict is `REQUEST_CHANGES`: T1 and T2 are major.

## T1 · major · error handling

- Location: `head/src/manifest.ts:67`
- Line: ``throw `no parcel with id ${id} in the manifest`;``
- Cause: `weightOf` throws a string. Its doc comment calls an unknown id an expected failure, but the change throws it instead of returning it in a result union, as `parseManifest` in the same file does.
- Trigger and consequence: a customer asks for an id that is not in the manifest, such as `P-9`. `weightLine` catches the string, and its `error instanceof Error` check is false, so the tracking page shows `P-9: something went wrong` and the reason is lost. A string has no stack trace, so a caller that logs it cannot tell where it came from.
- Rule: typescript-practices, error handling: throw only `Error` or a subclass; return an expected failure as `{ failure }` in a result union.
- Evidence: reading the function and its caller `weightLine` at `src/manifest.ts:73`. With the dependencies installed, `oxlint --type-aware` reports `typescript(only-throw-error)` at this line. No test asks for a missing id.
- A correct fix returns `{ failure: { type: "NotFound", message } }` from `weightOf` in a `{ data } | { failure }` result, and has `weightLine` show the failure's message.

## T2 · major · type safety

- Location: `head/src/labels.ts:11`
- Line: `const tracked = parcel as unknown as TrackedParcel;`
- Cause: `labelText` takes a `Parcel | TrackedParcel` and casts it through `unknown` to `TrackedParcel`, so the compiler no longer sees the case where the parcel has no tracking code. Its doc comment says parcels are labelled before the carrier accepts them, which is that case.
- Trigger and consequence: a parcel with no `trackingCode`, such as one `parseManifest` returns, makes `labelText` throw `TypeError: Cannot read properties of undefined (reading 'toUpperCase')`, and no label prints. Major, not critical: the review shows no caller where an untracked parcel is the common path.
- Rule: typescript-practices, type safety: never cast through `any` or `unknown` to make a type fit; give every `as` cast a comment saying why it holds.
- Evidence: reading the function and its doc comment. `tsc` and `oxlint --type-aware` report nothing here. The one test passes a tracked parcel.
- A correct fix narrows with `"trackingCode" in parcel` and handles the untracked case, or takes only a `TrackedParcel`.

## May report

These neither count for nor against the review. For example:

- Testing: no test covers a missing id in `weightOf`, or an untracked parcel in `labelText`. This may be folded into T1 and T2.
- Error handling: `weightLine` catches every error and shows a fixed text for any value that is not an `Error`.

## Must not report

Each of these would be a false finding.

- `const items: unknown[] = value;` in `parseManifest`. `Array.isArray` narrows `unknown` to `any[]`, and assigning that to `unknown[]` turns the checks back on. It is in the base, not the change.
- The catch in `parseManifest`, which narrows the caught value with `instanceof Error` before reading `message`. It is in the base.
- A missing property test for `parseManifest`. It is in the base, and untrusted-input tests belong to the testing area, which this version does not review.
- Anything in an area this version does not review, reported as a finding under that area.
- Anything in `base/` that the change does not touch.
