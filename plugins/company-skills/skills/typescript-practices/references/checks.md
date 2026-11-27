# TypeScript check suite

The TypeScript check suite is the set of checks that gate every pull request in a TypeScript repository. They run in CI, and CI is the gate. Run any of these tools locally when it helps you get a change right, but do not treat a local run as the gate.

This reference targets TypeScript 7.0 and Node 24 at minimum. The [examples package](../examples/package.json) pins TypeScript 7.0 and sets `engines.node` to `>=24`. CI checks it with the latest Node LTS release.

## Pinned versions

Every tool version is pinned. A repository's CI uses these versions.

| Tool | Version | Package |
| --- | --- | --- |
| typescript | `7.0.2` | `typescript` on npm |
| @biomejs/biome | `2.6.9` | `@biomejs/biome` on npm |
| oxlint | `1.95.0` | `oxlint` on npm |
| oxlint-tsgolint | `7.0.2008` | `oxlint-tsgolint` on npm |
| vitest | `5.1.1` | `vitest` on npm |
| @vitest/coverage-v8 | `5.1.1` | `@vitest/coverage-v8` on npm |
| fast-check | `4.11.0` | `fast-check` on npm |
| @fast-check/vitest | `0.5.0` | `@fast-check/vitest` on npm |
| publint | `0.3.25` | `publint` on npm |
| @arethetypeswrong/cli | `0.18.5` | `@arethetypeswrong/cli` on npm |
| osv-scanner | `v2.7.1` | `github.com/google/osv-scanner/v2/cmd/osv-scanner` |
| semgrep | `1.186.0` | `semgrep` on PyPI |

Each npm tool except attw is an exact devDependency, fixed by a committed `pnpm-lock.yaml` and installed with `pnpm install --frozen-lockfile`. A caret or tilde range is not pinned. pnpm itself is pinned in `packageManager`, such as `"packageManager": "pnpm@12.23.0"`. CI runs attw with `pnpm dlx @arethetypeswrong/cli@<version>`, because attw depends on its own exact TypeScript, which would put a second TypeScript in the lockfile. osv-scanner and semgrep are pinned in the workflow. semgrep has one pin, shared by every language's suite.

Two things float by choice. CI uses the latest Node LTS release, through `actions/setup-node` with `node-version: lts/*`. semgrep reads the latest `p/typescript` and `p/javascript` rulesets. Either can fail a pull request that did not cause the finding. Fix the finding.

The oxlint-tsgolint pin moves with the TypeScript pin, in the same pull request. Its version starts with the TypeScript version it is built on: `7.0.2008` is built on TypeScript `7.0.2`.

## The checks

- **Type check**: `tsc --noEmit -p <tsconfig> --checkers 4`, once for every `tsconfig` in the repository. TypeScript 7 can order some results by checker, so the `--checkers` count is fixed. Start from the template [assets/tsconfig.json](../assets/tsconfig.json). It sets the required compiler settings: `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, and `verbatimModuleSyntax`, plus `isolatedDeclarations` for a published package. A repository's own `tsconfig` may add settings, but must not turn these off.
- **Format and general lint**: `biome ci --error-on-warnings`. Start from the template [assets/biome.json](../assets/biome.json).
- **Type-aware lint**: `oxlint --type-aware --deny-warnings`, with oxlint-tsgolint installed. Start from the template [assets/oxlintrc.json](../assets/oxlintrc.json). It turns on the rules for un-awaited promises, unsafe `any` values, and throwing a non-`Error` value. A repository's own configuration may turn on more rules, but must keep these.
- **Tests and coverage**: `vitest run --coverage --coverage.provider=v8`. There is no coverage threshold.
- **Vulnerabilities**: `osv-scanner scan source -r .`, over every lockfile. It fails on any known vulnerability. #110 decides how to suppress an advisory that has no fix.
- **SAST**: `semgrep scan --config p/typescript --config p/javascript --error --metrics=off`, plus `--config .semgrep` when the repository has its own rules in `.semgrep/` at its root. Keep test files in the scan: a root `.semgrepignore` replaces semgrep's default list, which skips test directories.
- **Package shape**: publint (`publint --strict`) and attw (`attw --pack .`) for every package that does not set `"private": true`. Build the package first. A package that publishes ESM only, as new packages do, runs attw with `--profile esm-only`.
- **Untrusted input**: a function that parses or decodes untrusted input must have a fast-check property test, written with `@fast-check/vitest`. Untrusted input is bytes from outside the process, such as a request body, a file, or a message. In pull request CI, every property test runs with a fixed seed and a set number of runs: the Vitest setup file calls `fc.configureGlobal({ seed: 42, numRuns: 100 })`. Random seeds and longer runs go in a scheduled job, never in pull request CI. CI cannot tell that a property test is missing, so code review enforces this rule.

## The execution surface

Some files run their own code when the suite's tools build, lint, or test a change. A review runs no tool that would run such a file from the change until the user says yes:

- Vitest and Vite configuration files (`vitest.config.*`, `vite.config.*`, `vitest.workspace.*`), and the setup and global setup files they name.
- oxlint JavaScript plugins named in oxlint's configuration.
- Build configuration and `package.json` scripts, such as `tsup.config.*`, esbuild scripts, `prepare`, `prepack`, and `postpack`. publint and attw pack the package, so they wait for the yes when a build is needed.

`tsc --noEmit`, Biome, osv-scanner, and semgrep only read code.

## When a check is in place

A check is in place when it is a GitHub Actions step that:

- runs on `pull_request`, with no path filter unless a changes job that fails closed sits beside it;
- blocks: it has no `continue-on-error`, even when a later step enforces its result, no `|| true`, and no other way of ignoring the tool's exit status, such as a shell set without `-e` (`shell: bash {0}`), or a pipe such as `osv-scanner scan source -r . | tee out.txt` under the default shell, which sets no `pipefail`;
- covers every package, except test fixtures that contain planted defects. A `pnpm -r` or Turborepo run that skips a package without the script does not cover it;
- pins its version. `@latest`, `npx <tool>` with no version, and a range with no frozen install do not count. A step pinned at another exact version is still in place.

## Exemptions

A repository may leave a check out only through an exemption architecture decision record (ADR). The ADR is a file in `docs/adr/` on the repository's default branch, added through an issue and a reviewed pull request. It:

- names each check it exempts, and each package it covers;
- gives the reason;
- links the issue it came from and the pull request that adds it. The ADR counts once that pull request is merged.

An ADR leaves out only the checks and packages it names. A pull request cannot exempt itself by adding one.
