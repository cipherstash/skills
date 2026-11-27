# Output format

Read this in step 9. The review's output goes to the user in the conversation. It is not written to the repository or posted anywhere. It starts from golang-review's `output.md`, with the Go checks replaced by TypeScript's.

## Contents

- [Report shape](#report-shape)
- [Coverage and limits](#coverage-and-limits)
- [Fields](#fields)
- [Handing on](#handing-on)

## Report shape

Use this shape. Keep every section, even when it is empty, so a reader can see what the review covered. The example reviews a different change from any in this skill's tests.

````markdown
# TypeScript review: <target as given>

Reviewed `<base short SHA>`..`<head short SHA>` (full: `<base SHA>`..`<head SHA>`) in `<repository path or PR URL>`
TypeScript version: 7.0.2 (`packages/billing/package.json`, resolved by `pnpm-lock.yaml`); Node `>=24` (`engines.node`)
Compiler settings: `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` on; `lib` from `target: es2024` (`packages/billing/tsconfig.json`, extends `tsconfig.base.json`)
Source: typescript-review · <model ID, or unknown> · host <Claude Code, Codex, or unknown>
Skills: `typescript-review`, `typescript-practices`

## Checks

| Check | Scope | Outcome |
| --- | --- | --- |
| `tsc --noEmit -p packages/billing/tsconfig.json --checkers 4` | `packages/billing` | not run: needs the change's dependencies, which the review does not install |
| `biome lint --config-path=<worktree>` (2.6.9, fetched) | changed files | failed: `lint/suspicious/noExplicitAny` at `packages/billing/src/invoice.ts:18` |
| `oxlint -c .oxlintrc.json --disable-nested-config` (1.95.0, fetched) | changed files | passed; type-aware rules not run |
| `oxlint --type-aware` | changed files | not run: needs the change's dependencies, which the review does not install |
| `vitest run --coverage` | `packages/billing` | not run: needs the change's dependencies, which the review does not install. Command: `pnpm exec vitest run --coverage --coverage.provider=v8` in `packages/billing` |
| `osv-scanner`, `semgrep` | | not run: needs the network |
| `publint --strict`, `attw --pack . --profile esm-only` | `packages/billing` | not run: needs a build and the change's dependencies, which the review does not install |
| Declaration comparison | `packages/billing` | not run: needs the change's dependencies; compared by reading, see API changes |
| Type-aware lint in CI | `.` | failed: job `typescript / lint` on the head commit, `typescript(no-unsafe-member-access)` at `packages/billing/src/invoice.ts:21`, `<run URL>` |
| Tests and coverage in CI | `.` | passed: job `typescript / test` on the head commit, `<run URL>` |

## Check suite in CI

- osv-scanner: no workflow step runs it.
- Package shape: not in place: `attw` runs with `|| true` (`.github/workflows/ci.yml:52`).

## API changes

- Changed: `createInvoice(customerId: string): Promise<Invoice>` is now `createInvoice(customerId: string, currency: CurrencyCode): Promise<Invoice>` (`packages/billing/src/invoice.ts:12`). The new parameter has no default, so every existing caller stops compiling.
- Added: `CurrencyCode`, `refundInvoice`.
- Version: `2.3.0` at the base, and the change has no changeset, so it needs a major version.

## Coverage and limits

- Areas reviewed, in the order of SKILL.md's areas table, with the files read for each:
  1. Error handling: read `references/step-error-handling.md`, typescript-practices `references/error-handling.md`
  2. Correctness and edge cases: read `references/step-correctness.md`, typescript-practices `references/type-safety.md`, typescript-practices `references/error-handling.md`
  3. Type safety: read `references/step-type-safety.md`, typescript-practices `references/type-safety.md`
  4. Testing and coverage: read `references/step-testing.md`, typescript-practices `references/testing.md`
  5. Async and concurrency: read `references/step-async.md`, typescript-practices `references/async.md`
  6. Naming and style: read `references/step-naming.md`, typescript-practices `references/project-structure.md`
  7. Security: read `references/step-security.md`, typescript-practices `references/security.md`
  8. Performance: read `references/step-performance.md`, typescript-practices `references/performance.md`
  9. Dependency management: read `references/step-dependencies.md`, typescript-practices `references/dependencies.md`
  10. Documentation: read `references/step-documentation.md`, typescript-practices `references/project-structure.md`
  11. Breaking changes: read `references/step-breaking-changes.md`, typescript-practices `references/project-structure.md`, typescript-practices `references/dependencies.md`
- Areas not reviewed: none.
- Limits: `tsc`, type-aware lint, the tests, publint, attw, and the declaration comparison not run locally, so type errors, unsafe `any` values, test failures, and package shape rest on CI's results and reading; osv-scanner and semgrep not run.

## Findings

### T1 · major · `packages/billing/src/invoice.ts:18` · webhook body used as `any`

- Area: type safety
- Cause: the change types the payment provider's webhook body as `any` and reads `body.amount.total` from it with no check.
- Trigger and consequence: a refund event, whose body has no `amount` field, makes the handler throw `TypeError: Cannot read properties of undefined (reading 'total')`, so the provider retries the event until it gives up and the refund is never recorded.
- Rule: typescript-practices type safety, "Use `unknown`, not `any`, for a value whose type you do not know. Narrow it before use."
- Evidence: read at `packages/billing/src/invoice.ts:18` to `:21`. Biome reports `noExplicitAny` at line 18. CI's type-aware lint reports `no-unsafe-member-access` at line 21.
- Fix: type the body as `unknown` and parse it with the schema the package already uses for other webhook events, returning a `{ failure }` for a body that does not match.
- Source: typescript-review · <model ID>

### T2 · minor · `packages/billing/src/currency.ts:9` · string thrown for an unknown currency

- Area: error handling
- Cause: `toMinorUnits` throws the string `unsupported currency` for a currency code it does not know.
- Rule: typescript-practices error handling, "Throw only `Error` or a subclass."
- Evidence: read at `packages/billing/src/currency.ts:9`. No caller in the repository catches it, so no consequence is shown beyond the missing stack trace.
- Fix: return `{ failure: { type: "UnsupportedCurrency", message } }`, since the currency code comes from the customer's settings.
- Source: typescript-review · <model ID>

### T3 · major · `packages/billing/src/invoice.ts:12` · new required parameter on an exported function

- Area: breaking changes
- Cause: the change adds a required `currency` parameter to `createInvoice`, which the package's entry point exports.
- Trigger and consequence: a user who updates within `^2.3.0` gets this version, and each call `createInvoice(id)` stops compiling.
- Evidence: the exports of `packages/billing/src/index.ts` read at the base and the head. The package is at `2.3.0` and the change adds no changeset.
- Fix: give `currency` a default of the customer's currency, or add a changeset that marks the release `major`.
- Source: typescript-review · <model ID>

<further findings, most severe first>

Next: `review-cross-check`, `review-post`, `review-fix`, if you ask.

## Verdict

REQUEST_CHANGES: <one to three sentences: what blocks the change, and any limit the reader must know.>
````

## Coverage and limits

Every one of the eleven areas is listed once, as reviewed or not reviewed with the reason: `not in scope at the user's request`, cut for scope, or `step reference not read`. An area is reviewed only if its step reference was read; otherwise it is listed as not reviewed, `step reference not read`, with no findings under it.

## Fields

- **Reviewed**: full SHAs for base and head. For uncommitted changes, write `HEAD <SHA> plus uncommitted changes`. A snapshot has no commit for `review-post` to post against, so say the user must commit before posting.
- **TypeScript version** and **Compiler settings**: one line each per package when the change touches several, with the file each came from. Write `not found` where a package names no `typescript` version, and say the review used TypeScript 7.0.
- **Checks**: one row per check, with the exact command, the tool's version, and the scope. The outcome is `passed`, `failed: <evidence>`, or `not run: <reason>`, as `checks.md` defines them. A check that needs the change's dependencies gives the command the user can run. Each suite check CI ran on the head commit is its own row, with the job, CI's outcome, and the run's URL; write `no CI result for the head commit` with the reason when there is none. A local run of a suite tool is evidence for a finding, not the gate's result.
- **Check suite in CI**: one line for each suite check that is not in place in CI at the head, as `checks.md` describes under "The check suite in CI". Each line says what is missing. Write `All in place.` when none is missing. Write `not compared: <reason>` when the review could not compare CI with the suite. That is also a limit. A missing check is a line here, not a finding. A check the change removes or weakens is also a finding.
- **API changes**: for each changed published package, every removed, renamed, or changed export and `exports` entry, the additions in one line, and the version note, as `step-breaking-changes.md` describes. Write `None.` when the public API is unchanged, `not published: the package is private` for a private package, and `not compared: <reason>` when the review could not compare it, which is also a limit. Leave the section out only when breaking changes are not in scope at the user's request.
- **Coverage and limits**: as [Coverage and limits](#coverage-and-limits) above. A reviewed area lists the files read for it in step 7: its step reference and each typescript-practices reference, by path. A typescript-practices reference the table names for a reviewed area but not read is a limit of that area. If the skill could not be loaded, write `typescript-practices not loaded:` and the references not read under limits. Every check not run is a limit, as is any change to the user's tree found in step 9.
- **Findings**: most severe first, numbered `T1`, `T2`, and so on. A finding with no single line gives the files and says `design-level`. A deleted line gives the base line and says `deleted`. Write `Rule:` when the finding rests on a rule, and `Trigger and consequence:` when it rests on behaviour. Write both when both apply. With no findings, write `No findings.` and keep the coverage section, so the result is read as clean only within that coverage.
- **Verdict**: the last section. `REQUEST_CHANGES` when any finding is critical or major, otherwise `APPROVE`. An `APPROVE` summary names the limits and areas not reviewed.

## Handing on

The findings are already in the shape the other review skills take: file and line, claim, trigger, severity in `critical`, `major`, or `minor`, and source. Just above the verdict, in one line, name the next steps that apply, so the verdict stays last:

- `review-cross-check` checks the findings against a pull request's existing review comments.
- `review-post` posts them to the pull request as a comment review, against the reviewed head commit.
- `review-fix` fixes them.

Do not run any of these unless the user asks.
