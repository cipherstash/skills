---
name: golang-review
description: Reviews a Go change — a diff, branch, commit range, or pull request — and reports findings with file and line, the checks it ran and could not run, and an APPROVE or REQUEST_CHANGES verdict. Covers error handling and concurrency safety, using go vet and race-enabled tests as evidence and golang-practices' references as the rules. Use when asked to review Go code, a Go pull request or branch, or to check a Go change for bugs before merge. Read-only. Does not write Go (golang-practices), fix findings (review-fix), or post to a pull request (review-post).
argument-hint: "[PR number or URL, branch, commit range, or diff]"
---

# golang-review

Review one Go change and report what is wrong with it. A finding is a claim about the change, and every finding carries its evidence: a location, the cause, what triggers it and what goes wrong, or the rule it breaks. A check that could not run is a **limit** of the review, reported as one, never a pass and never a defect.

The steps run in order in one session. They need no subagents, so the skill works the same on hosts without them.

## Inputs

- **The target**: a pull request (number or URL), a branch, a commit range, or a diff (the uncommitted changes, a patch file, or a pasted diff). A request with no target named, such as "review my Go changes", resolves to the uncommitted changes or the current branch, as [references/target.md](references/target.md) describes.
- **Areas** (optional): a request that names areas, such as "just check the concurrency", reviews those areas only. The others are listed as not reviewed at the user's request.

## Read-only

The review leaves the user's repository as it found it. Checks run in a temporary worktree, which is removed on every exit, including a stop. The review:

- does not edit, stage, stash, check out, or reset anything in the user's working tree;
- does not install anything: no `go get`, `go mod download`, `go mod tidy`, `go install`, or toolchain download;
- does not post to a pull request, reply to or resolve a thread, or submit a review on GitHub. The verdict lives in the report only.

Read every command before running it, and run only what [references/checks.md](references/checks.md) allows. Running `go test` runs the change's own code on this machine, so that reference says what to read first and when to leave the tests unrun.

## Steps

1. **Resolve the target.** Follow [references/target.md](references/target.md) to find the base and head of the change, list the changed Go files and their packages, and record the reviewed state: full base and head commit SHAs, or a snapshot of the uncommitted changes on top of a named commit. With no target you can identify, stop and report what you looked for and what the review needs: a PR number or URL, a branch, a commit range, or a diff. Do not ask a question. With no Go files in the change, as that reference lists them (`.go` files, cgo and assembly sources in Go packages, `.syso` objects, `go.mod`, `go.sum`, `go.work`), stop and report that there is no Go change to review. Completion: the reviewed state is recorded and every changed Go file is listed, or the run has stopped with its report.

2. **Prepare the tree.** Create the temporary worktree at the head with `git worktree add`, as [references/target.md](references/target.md) describes, never a `git archive` export or a copy, and record `git status --porcelain` for the user's tree. Without a local clone the review reads the change through the host's GitHub tools and runs no checks; record that as a limit. Completion: the worktree path is recorded, or the limit is.

3. **Read the Go version.** For each module the change touches, read the `go` line in its `go.mod`, and the `toolchain` line if there is one. Record the version before applying any rule that depends on it, such as how a closure captures a loop variable (per-iteration from Go 1.22) or which standard-library API exists. A module with no `go` line is reviewed as Go 1.16, which is what the go command assumes, and the report says so. Completion: every touched module has its version recorded.

4. **Load golang-practices.** Invoke the `golang-practices` skill by name: the Skill tool in Claude Code, where it may be namespaced as `company-skills:golang-practices`, or `$golang-practices` in Codex. Loading it gives its directory, and the practices references in the table below resolve from there. Use it for its rules and references only. It is written for writing Go, and the review's own steps decide what is a finding. If it cannot be loaded, continue with this skill's step references alone, and record each practices reference not read as a coverage limit. Completion: golang-practices is loaded and its directory known, or the limit is recorded.

5. **Run the checks.** Follow [references/checks.md](references/checks.md): read the changed code the tests will run, then run `go vet` and race-enabled `go test` over the changed packages in the worktree, with the read-only settings it lists. Record each check as passed, failed with its output, or not run with the reason. Completion: every check in that reference has one of those three outcomes.

6. **Review each area.** Work through the areas in the table below in priority order. For each area this skill covers, read its step reference and the practices reference it names, then examine every changed hunk for that area, following calls into unchanged code where that is needed to show a consequence. List candidate findings with their evidence. An area this skill does not yet cover is listed in the report as not reviewed. Completion: every changed Go hunk has been examined for every covered area in scope.

7. **Test each finding.** Keep a candidate only if it meets the finding contract below, and give it a severity. Drop a departure from preferred practice that has no consequence and breaks no cited rule. Merge candidates that share one root cause into one finding that lists every location. Completion: every remaining finding meets the contract.

8. **Report.** Remove the worktree. Compare `git status --porcelain` with the record from step 2, and report any difference. Then write the report in the format of [references/output.md](references/output.md): the reviewed state, the checks and their outcomes, coverage and limits naming every area not reviewed (in this version, at least the eight marked "Not yet covered"), the findings most severe first, a one-line list of the next steps that apply, and last the verdict with a short summary. Completion: the worktree is gone and the report ends with its verdict.

## Areas

The ten areas of the Go review checklist, in priority order. Priority sets the order of work and what to cut first when the request or the context is narrow. It is not the severity of a finding.

| Order | Area | Priority | Step reference | Practices reference |
| --- | --- | --- | --- | --- |
| 1 | Error handling | High | [references/step-error-handling.md](references/step-error-handling.md) | `references/error-handling.md` |
| 2 | Correctness and edge cases | High | Not yet covered | |
| 3 | Testing and coverage | High | Not yet covered | |
| 4 | Concurrency safety | Medium | [references/step-concurrency.md](references/step-concurrency.md) | `references/concurrency.md` |
| 5 | Naming and style | Medium | Not yet covered | |
| 6 | Security | Medium | Not yet covered | |
| 7 | Performance | Medium | Not yet covered | |
| 8 | Dependency management | Medium | Not yet covered | |
| 9 | Documentation | Low | Not yet covered | |
| 10 | Breaking changes | Low | Not yet covered | |

An area marked "Not yet covered" is reported under coverage as not reviewed by this version of the skill. A defect you notice in one of those areas while working on another is still reported if it meets the finding contract, under the area it belongs to.

## Finding contract

Every finding has:

- **Location**: the repository-relative path and the line or range at the head. A deleted line is located at the base and marked as deleted. A design-level finding names the files and says it has no single line.
- **Cause**: what in the change causes it. A defect that the change does not introduce or make reachable is out of scope.
- **Trigger and consequence**, or **rule**: the input, state, or timing that makes it fail and what goes wrong then; or the golang-practices rule it breaks, quoted or named with its reference. Without either, it is not a finding.
- **Evidence**: the lines read, and the output of any check that shows it, such as a race report. Say which parts are observed and which are inferred.
- **Severity**: one of `critical`, `major`, or `minor`, the vocabulary `review-cross-check`, `review-post`, and `review-fix` take unchanged.
  - `critical`: the review traces a realistic trigger to severe harm outside the function's result: a crash in a common path, a security exposure, or wrong data that is stored or sent outside the program.
  - `major`: wrong behaviour under a concrete trigger. A dropped error, a data race, a deadlock, or a goroutine leak that grows with use is major, even when it yields a wrong result, unless the review shows it reaching critical harm.
  - `minor`: a bounded defect, or a broken rule with no demonstrated runtime consequence.
- **Fix**: a short, concrete correction. Name only APIs that exist in the module's Go version and packages it already uses.
- **Source**: `golang-review` and the model that ran it, or `unknown`.

## Verdict

End the report with `APPROVE` or `REQUEST_CHANGES` and a summary of one to three sentences.

- `REQUEST_CHANGES` when any finding is critical or major.
- `APPROVE` otherwise. The summary then names any limit or area not reviewed, so an approval is never read as wider than the review was.

The verdict is a recommendation in the report. To publish findings, the user runs `review-post`, which posts a comment review only. To fix them, the user runs `review-fix`.
