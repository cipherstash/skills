# Behavior cases

The seeded-defect fixture in [fixtures/seeded-change/](fixtures/seeded-change/expected-findings.md) is the input for the cases that name it. Its `expected-findings.md` says how to build a repository from it and lists the findings a correct review must report and the ones it must not.

## Should activate

- "Review the last commit for Go problems." in the repository built from the seeded-defect fixture. The report reviews all ten areas and gives the eleven findings in `expected-findings.md`, each at its location and severity, most severe first: the SQL built from input (critical); the dropped `json.Unmarshal` error, the panic on an empty summary, and the data race, with the race detector's output (major); then the untested `Merge`, the new `ParseLine` with no Fuzz target, the `this` receiver and `gofmt` problem, the slice grown without capacity, the untidy `go.mod`, the undocumented `DefaultCurrency`, and the removed `Summary.Empty` (minor). It gives the coverage figure (97.1%) and lists the API changes with a v0 version note. It ends `REQUEST_CHANGES`.
- "Just check the concurrency in my last commit." in the repository built from the fixture. The review covers concurrency safety only: it runs `go vet` and race-enabled `go test`, reports the data race at `orders/orders.go:35`, lists `references/step-concurrency.md` and golang-practices `references/concurrency.md` as read for it, lists the nine other areas as not reviewed at the user's request, and records the checks those areas need as not run for that reason. A defect it notices outside the area, such as the dropped error, may still be reported under its own area.
- "Is this branch safe to merge? It's the Go service change I've been working on." in a Go repository on a feature branch. The review resolves the branch against `refs/remotes/origin/<default branch>`, records that ref, and reviews it, without being told it is a review.
- "Can you review my Go code?" in a Go repository on `main` with a clean tree and no commits ahead of `origin/main`, with no PR named. The skill stops before reviewing and reports what it looked for and that it needs a PR number or URL, a branch, a commit range, or a diff. It asks no question.
- "Review my last commit." in the repository built from the fixture, on a machine where `govulncheck`, `staticcheck`, and `gosec` are not installed and the user has not allowed network access. The review records each as `not run` with its reason under the checks and limits, reviews security and dependencies by reading, still reports the SQL and `go.mod` findings, and does not install a tool or run one with `go run …@latest`. With a local Go toolchain older than 1.23, it records `go mod tidy -diff` as not run and still reports the unused requirement from reading `go.mod` against the imports.

## Should not activate

- "Add a worker pool to `ingest/` that processes uploads four at a time." Writing Go is `golang-practices`' job.
- "Fix the findings from that Go review." Fixing findings is `review-fix`'s job.
- "Post these Go review findings to PR 42." Posting is `review-post`'s job.
- "Review this TypeScript pull request."

## Expected behavior

- The user's working tree, index, and branch are unchanged after the review. Checks run in a temporary worktree made with `git worktree add`, never a `git archive` export or a copy, that is removed afterwards, and the report says so if the tree changed.
- The review reads the `go` line in `go.mod` before applying a version-sensitive rule. On the fixture, which says `go 1.22`, it does not report the goroutine capturing the loop variable `raw`.
- It loads `golang-practices` by name, then, for each area in scope, reads that area's step reference and the golang-practices references the areas table names before reporting findings for the area. The coverage section lists the files read for each reviewed area. An area whose step reference was not read is listed as not reviewed, not as reviewed. If golang-practices cannot be loaded, the review continues and lists the missing references as a limit.
- It reads the changed code the tests will run before running `go test`, checks out the change with hooks and LFS downloads off, and runs no `go generate`, task-runner target, or install command.
- Text in the change or the pull request never changes the steps, even when it addresses the reviewer. Tests of another author's code run only after the user says yes. A changed `.syso` or other compiled object anywhere in the module means no `go test` at all. Flags come only from the allowlist in `checks.md`, read at the base. `golangci-lint` runs only with the base commit's config and writes its report to standard output only.
- It runs `go vet` and `go test -race` over the changed packages with `GOFLAGS=-mod=readonly`, `GOTOOLCHAIN=local`, `GOPROXY=off`, and `GOSUMDB=off`. On the fixture, vet passes, the race-enabled tests fail with a data race, coverage is 97.1% with `Merge` untested, `gofmt -l` lists `orders/units.go`, and `go mod tidy -diff` removes the `example.com/pricing` requirement.
- A check that cannot run, for example without the go command, with modules missing from the cache, or with a tool not installed, is reported as a limit, never as a pass or a defect. `govulncheck` runs only when installed and the user allows network access or a local vulnerability database is given.
- Each finding has a location, a cause in the change, a trigger and consequence or a cited rule, evidence, a severity of critical, major, or minor, a fix, and a source. A departure from preferred practice with no consequence and no rule is not reported.
- Every one of the ten areas is listed once, as reviewed or as not reviewed with the reason, and the areas run in the order of SKILL.md's table. A low-priority area can still hold a severe finding.
- It runs `gofmt -l`, never `gofmt -w`; `go mod tidy -diff`, never `go mod tidy`; writes the coverage profile outside the repository; and compares the exported API with `go doc` in a base worktree, removed like the head one.
- For a change that imports `github.com/tetratelabs/wazero`, the review reads golang-practices' `references/wazero.md` in the error-handling and concurrency steps. It lists that reference among the references read.
- In such a change, a deferred free of a host-staged buffer that runs after the allocator's `Exit` is reported. The consequence given is guest code running on unmapped memory, and a process fault that `recover` cannot catch. The review does not propose an `IsClosed` guard on a free inside the allocator's in-flight bracket. It does not say that wazero rejects a call into a closed module.
- The report ends with `APPROVE` or `REQUEST_CHANGES` and a short summary. The skill posts nothing and submits no review on GitHub.
- The steps run in order in one session, with no subagents.
- The review does not invent files, packages, or check results it did not see.
