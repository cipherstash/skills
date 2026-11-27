# Output format

Read this in step 8. The review's output goes to the user in the conversation. It is not written to the repository or posted anywhere. It starts from golang-review's `output.md`, with the Go checks replaced by TypeScript's.

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
| `publint`, `attw` | | not run: breaking changes not reviewed in this version |
| Type-aware lint in CI | `.` | failed: job `typescript / lint` on the head commit, `typescript(no-unsafe-member-access)` at `packages/billing/src/invoice.ts:21`, `<run URL>` |
| Tests and coverage in CI | `.` | passed: job `typescript / test` on the head commit, `<run URL>` |

## Check suite in CI

not compared: this version has no repository standards step.

## Coverage and limits

- Areas reviewed, in the order of SKILL.md's areas table, with the files read for each:
  1. Error handling: read `references/step-error-handling.md`, typescript-practices `references/error-handling.md`
  3. Type safety: read `references/step-type-safety.md`, typescript-practices `references/type-safety.md`
- Areas not reviewed: Correctness and edge cases, Testing and coverage, Async and concurrency, Naming and style, Security, Performance, Dependency management, Documentation, and Breaking changes: no step for this area yet.
- Limits: `tsc`, type-aware lint, and the tests not run locally, so type errors, unsafe `any` values, and test failures rest on CI's results; osv-scanner and semgrep not run.

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

<further findings, most severe first>

Next: `review-cross-check`, `review-post`, `review-fix`, if you ask.

## Verdict

REQUEST_CHANGES: <one to three sentences: what blocks the change, the areas not reviewed, and any limit the reader must know.>
````

## Coverage and limits

Every one of the eleven areas is listed once, as reviewed or not reviewed with the reason. This version has a step for Error handling and Type safety only. Each of the other nine areas, Correctness and edge cases, Testing and coverage, Async and concurrency, Naming and style, Security, Performance, Dependency management, Documentation, and Breaking changes, is listed as not reviewed with the reason `no step for this area yet`. An area in scope whose step reference was not read is listed as not reviewed with the reason `step reference not read`, with no findings under it. An area the user left out is listed as `not in scope at the user's request`.

## Fields

- **Reviewed**: full SHAs for base and head. For uncommitted changes, write `HEAD <SHA> plus uncommitted changes`. A snapshot has no commit for `review-post` to post against, so say the user must commit before posting.
- **TypeScript version** and **Compiler settings**: one line each per package when the change touches several, with the file each came from. Write `not found` where a package names no `typescript` version, and say the review used TypeScript 7.0.
- **Checks**: one row per check, with the exact command, the tool's version, and the scope. The outcome is `passed`, `failed: <evidence>`, or `not run: <reason>`, as `checks.md` defines them. A check that needs the change's dependencies gives the command the user can run. Each suite check CI ran on the head commit is its own row, with the job, CI's outcome, and the run's URL; write `no CI result for the head commit` with the reason when there is none. A local run of a suite tool is evidence for a finding, not the gate's result.
- **Check suite in CI**: `not compared: this version has no repository standards step`.
- **Coverage and limits**: as [Coverage and limits](#coverage-and-limits) above. A reviewed area lists the files read for it in step 6: its step reference and each typescript-practices reference, by path. A typescript-practices reference the table names for a reviewed area but not read is a limit of that area. If the skill could not be loaded, write `typescript-practices not loaded:` and the references not read under limits. Every check not run is a limit, as is any change to the user's tree found in step 8.
- **Findings**: most severe first, numbered `T1`, `T2`, and so on. A finding with no single line gives the files and says `design-level`. A deleted line gives the base line and says `deleted`. Write `Rule:` when the finding rests on a rule, and `Trigger and consequence:` when it rests on behaviour. Write both when both apply. With no findings, write `No findings.` and keep the coverage section, so the result is read as clean only within that coverage.
- **Verdict**: the last section. `REQUEST_CHANGES` when any finding is critical or major, otherwise `APPROVE`. An `APPROVE` summary names the limits and areas not reviewed.

## Handing on

The findings are already in the shape the other review skills take: file and line, claim, trigger, severity in `critical`, `major`, or `minor`, and source. Just above the verdict, in one line, name the next steps that apply, so the verdict stays last:

- `review-cross-check` checks the findings against a pull request's existing review comments.
- `review-post` posts them to the pull request as a comment review, against the reviewed head commit.
- `review-fix` fixes them.

Do not run any of these unless the user asks.
