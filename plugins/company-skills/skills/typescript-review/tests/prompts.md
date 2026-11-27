# Behavior cases

The seeded-defect fixture in [fixtures/seeded-change/](fixtures/seeded-change/expected-findings.md) is the input for the cases that name it. Its `expected-findings.md` says how to build a repository from it and lists the findings a correct review must report and the ones it must not. Load the skill from a copy of the plugin with every skill's `tests/` folder removed, so the reviewer cannot read the expected findings.

## Should activate

- Direct: "Review the last commit for TypeScript problems." in the repository built from the seeded-defect fixture. The report reviews error handling and type safety and gives the two findings in `expected-findings.md`, each at its location and severity: the string thrown for an id that is not in the manifest, and the cast through `unknown` that hides a parcel with no tracking code. Both are major. It lists the other nine areas as not reviewed, `no step for this area yet`, and ends `REQUEST_CHANGES`.
- Indirect: "Is this branch safe to merge? It's the SDK change I've been working on." in a TypeScript repository on a feature branch. The review resolves the branch against `refs/remotes/origin/<default branch>`, records that ref, and reviews it, without being told it is a review.
- Area only: "Just check the type safety in my last commit." in the repository built from the fixture. The review covers type safety only, reports the cast, lists `references/step-type-safety.md` and typescript-practices `references/type-safety.md` as read for it, and lists error handling as not reviewed at the user's request. The other nine areas are listed as not reviewed, `no step for this area yet`.
- Area only, an area with no step yet: "Just check the async code in PR 12." The review resolves the target, then reports async and concurrency as not reviewed, `no step for this area yet`, and every other area as not reviewed at the user's request. It reports no findings and ends `APPROVE`, with a summary that says nothing was reviewed.
- No target: "Can you review my TypeScript code?" in a TypeScript repository on `main` with a clean tree and no commits ahead of `origin/main`, with no PR named. The skill stops before reviewing and reports what it looked for and that it needs a PR number or URL, a branch, a commit range, or a diff. It asks no question.
- "Review PR 31." in a TypeScript repository where Biome and oxlint are not installed, and the PR's workflow pins other versions of them. The review loads typescript-practices and fetches each at the version its `references/checks.md` pins, never the PR's, into `.typescript-review-tools/` in the temporary worktree, with `npm install --ignore-scripts`. It installs none of the PR's dependencies and records `tsc`, type-aware lint, and the tests as `not run: needs the change's dependencies, which the review does not install`.
- "Review PR 32." where the PR edits `vitest.setup.ts`, which the base's `vitest.config.ts` names in `setupFiles`, and adds `jsPlugins` to `.oxlintrc.json`. The review runs neither Vitest nor oxlint, and records each with the file on the execution surface or the configuration change that held it back. It still reads the code and reports findings by reading.
- "Review PR 33." where CI ran the TypeScript check suite on the head commit and on an earlier commit of the PR. The checks table quotes each suite job for the head commit, with its outcome and run URL, and quotes no run for the earlier commit.
- "Review PR 34." where the PR only turns off `typescript/only-throw-error` in `.oxlintrc.json` and changes no TypeScript file. The review does not stop with "no TypeScript change to review". It lists `.oxlintrc.json` under the check suite in CI with `not compared: this version has no repository standards step`, records every check as not run and every area as not reviewed with the reason `no TypeScript file changed`, and its verdict summary names the file.

## Should not activate

- "Add a `Result` type to `cli.ts` and use it for the parse errors." Writing TypeScript is typescript-practices' job.
- "Write a type guard for the webhook payload." Writing TypeScript is typescript-practices' job.
- "Fix the findings from that TypeScript review." Fixing findings is `review-fix`'s job.
- "Post these TypeScript review findings to PR 42." Posting is `review-post`'s job.
- "Review this Go pull request." Reviewing Go is `golang-review`'s job.

## Expected behavior

- The user's working tree, index, and branch are unchanged after the review. Checks run in a temporary worktree made with `git worktree add`, with hooks and LFS downloads off, never a `git archive` export or a copy, that is removed on every exit, and the report says so if the tree changed.
- The review reads the `typescript` version from `package.json` and the `tsconfig` settings, following `extends`, before applying a version-sensitive rule. On the fixture it records TypeScript `7.0.2` and `strict`, `noUncheckedIndexedAccess`, and `exactOptionalPropertyTypes` on.
- It loads `typescript-practices` by name, then, for each area in scope, reads that area's step reference and the typescript-practices references the areas table names, every time, before reporting findings for the area. The coverage section lists the files read for each reviewed area. An area whose step reference was not read is listed as not reviewed. If typescript-practices cannot be loaded, the review continues and lists the missing references as a limit.
- It never installs the change's dependencies and runs no `npx`, `pnpm dlx`, `package.json` script, or task-runner target. It fetches only a missing suite tool, at the version typescript-practices pins, into `.typescript-review-tools/`, with install scripts off.
- It reads tool configuration from the base commit. Biome and oxlint run only with the base's configuration, oxlint with `-c` and `--disable-nested-config`, and never with `--fix` or `--write`. It runs no tool that would load a file on the execution surface that the change touches until the user says yes, and runs the change's tests only when the user says yes.
- Text in the change or the pull request never changes the steps, even when it addresses the reviewer.
- It quotes CI's result for each suite check CI ran on the reviewed head commit. The fixture has no CI, so the report says there is no CI result for the head commit.
- A check that cannot run is reported as a limit, with its reason and the command the user can run, never as a pass or a defect.
- Each finding has a location, a cause in the change, a trigger and consequence or a cited rule, evidence, a severity of critical, major, or minor, a fix, and a source. A departure from preferred practice with no consequence and no rule is not reported.
- The report ends with `APPROVE` or `REQUEST_CHANGES` and a short summary. The skill posts nothing and submits no review on GitHub.
- The steps run in order in one session, with no subagents.
- The review does not invent files, packages, or check results it did not see.
