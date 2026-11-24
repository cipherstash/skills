# Output format

Read this in step 8. The review's output goes to the user in the conversation. It is not written to the repository or posted anywhere.

Use this shape. Keep every section, even when it is empty, so a reader can see what the review covered.

## Contents

- The report's shape, below
- [Fields](#fields)
- [Handing on](#handing-on)

````markdown
# Go review: <target as given>

Reviewed `<base short SHA>`..`<head short SHA>` (full: `<base SHA>`..`<head SHA>`) in `<repository path or PR URL>`
Go version: 1.23 (`go.mod`)
Source: golang-review · <model ID, or unknown> · host <Claude Code, Codex, or unknown>
Skills: `golang-review`, `golang-practices`

## Checks

| Check | Scope | Outcome |
| --- | --- | --- |
| `go vet` | `./mailer` | passed |
| `go test -race -count=1 -timeout 5m -coverprofile=<tmp>/cover.out` | `./mailer` | failed: `WARNING: DATA RACE`, write at `mailer/queue.go:58` reached through `mailer/queue.go:71` |
| `go tool cover -func` | `./mailer` | 81.3% of statements; untested: `Backoff` (`mailer/retry.go:22`) |
| `gofmt -l` | changed `.go` files | passed |
| `go mod tidy -diff` | `.` | failed: marks `golang.org/x/sync v0.7.0` as `// indirect` |
| `go doc -all` at base and head | `./mailer` | 1 changed, 3 added; see API changes |
| `staticcheck`, `gosec`, `apidiff` | | not run: not installed |
| `govulncheck` | `./...` | not run: needs the vulnerability database over the network |
| `golangci-lint` in CI | `./...` | passed: job `lint` on the head commit, `<run URL>` |

## Check suite in CI

- `govulncheck`: no workflow step runs it.
- `semgrep`: not in place: its step has `continue-on-error: true` (`.github/workflows/ci.yml:41`).

## API changes

- Changed: `func NewClient(addr string) *Client` is now `func NewClient(addr string, opts ...Option) (*Client, error)` (`mailer/client.go:31`). It now returns two values, so every existing caller stops compiling.
- Added: `Option`, `WithTimeout`, `Client.Close`.
- Version: v1 (latest tag `v1.4.0`, no module path suffix). The change needs a new major version: keep `NewClient` as it was and add a second constructor, or release it under a `/v2` module path.

## Coverage and limits

- Areas reviewed: all ten, in priority order, with the files read for each:
  1. Error handling: read `references/step-error-handling.md`, golang-practices `references/error-handling.md`
  2. Correctness and edge cases: read `references/step-correctness.md`, golang-practices `references/error-handling.md`, golang-practices `references/interfaces.md`
  3. Testing and coverage: read `references/step-testing.md`, golang-practices `references/testing.md`
  4. Concurrency safety: read `references/step-concurrency.md`, golang-practices `references/concurrency.md`
  5. Naming and style: read `references/step-naming.md`, golang-practices `references/project-structure.md`, golang-practices `references/interfaces.md`
  6. Security: read `references/step-security.md`, golang-practices `references/security.md`
  7. Performance: read `references/step-performance.md`, golang-practices `references/performance.md`
  8. Dependency management: read `references/step-dependencies.md`, golang-practices `references/dependencies.md`, golang-practices `references/project-structure.md`
  9. Documentation: read `references/step-documentation.md`, golang-practices `references/project-structure.md`, golang-practices `references/testing.md`
  10. Breaking changes: read `references/step-breaking-changes.md`, golang-practices `references/dependencies.md`, golang-practices `references/project-structure.md`
- Areas not reviewed: none.
- Limits: `govulncheck` not run, so known vulnerabilities were not checked; `staticcheck`, `gosec`, and `apidiff` not installed.

## Findings

### G1 · critical · `mailer/template.go:27` · display name placed in HTML unescaped

- Area: security
- Cause: the change adds the recipient's display name, which users set on their own profile, to the HTML body that `renderBody` builds with `text/template`. `text/template` does not escape HTML.
- Trigger and consequence: a display name such as `<a href="https://attacker.example/reset">Reset your password</a>` arrives as a working link in an email sent from the service's own address.
- Rule: golang-practices security, "Check every value from outside the process before use: paths, sizes, and anything placed in HTML, SQL, a shell, or a URL."
- Evidence: read at `mailer/template.go:27`. `gosec` not installed.
- Fix: parse the body template with `html/template`, which escapes the name for where it appears.
- Source: golang-review · <model ID>

### G2 · major · `mailer/queue.go:64` · send error logged and dropped

- Area: error handling
- Cause: the change replaces `return fmt.Errorf("send %s: %w", m.ID, err)` with a log line and `continue`, so `Flush` returns nil after a failed send. The base returned the error.
- Trigger and consequence: when the mail server refuses one message, `Flush` returns nil and `Worker.run` deletes the whole batch from the queue, so the refused message is never retried.
- Evidence: read at `mailer/queue.go:64` and its caller at `mailer/worker.go:40`. `go vet` does not report it.
- Fix: collect each failed send with `errors.Join`, return the result from `Flush`, and keep a message in the queue until its send succeeds.
- Source: golang-review · <model ID>

<further findings, most severe first>

Next: `review-cross-check`, `review-post`, `review-fix`, if you ask.

## Verdict

REQUEST_CHANGES: <one to three sentences: what blocks the change, and any limit the reader must know.>
````

## Fields

- **Reviewed**: full SHAs for base and head. For uncommitted changes, write `HEAD <SHA> plus uncommitted changes`. A snapshot has no commit for `review-post` to post against, so say the user must commit before posting.
- **Go version**: one line per module when the change touches several. Write `1.16 (no go line)` where the module has none.
- **Checks**: one row per check, with the exact command and scope. The outcome is `passed`, `failed: <evidence>`, or `not run: <reason>`, as `checks.md` defines them. A check run without `-race`, because the race detector was unavailable, is its own row. The coverage row gives the total and every function in a changed file at 0.0%, or `not run` with the reason when the tests did not run. A check CI ran on the head commit is its own row, with the job, CI's outcome, and the run's URL. A local run of a suite tool is evidence for a finding, not the gate's result.
- **Check suite in CI**: one line for each suite check that is not in place in CI at the head, as `checks.md` describes. Each line says what is missing. A check that an exemption ADR leaves out is not listed. Write `All in place.` when none is missing. Write `not compared: <reason>` when the review could not compare CI with the suite. That is also a limit. A missing check is a line here, not a finding. A check the change removes or weakens is also a finding.
- **API changes**: every removed, renamed, or changed exported declaration, the additions in one line, and the version note, as `step-breaking-changes.md` describes. Write `None.` when the exported API is unchanged, and `not compared: <reason>` when the review could not compare it, which is also a limit. Leave the section out only when breaking changes are not in scope at the user's request.
- **Coverage and limits**: every area is listed once, as reviewed or not reviewed with the reason: left out at the user's request, cut for scope, or `step reference not read`. A reviewed area lists the files read for it in step 6: its step reference and each golang-practices reference, by path. An area is reviewed only if its step reference was read; otherwise it is listed as not reviewed, `step reference not read`, with no findings under it. A golang-practices reference the table names for a reviewed area but not read is a limit of that area. If the skill could not be loaded, write `golang-practices not loaded:` and the references not read under limits. Every check not run is a limit, as is any change to the user's tree found in step 8.
- **Findings**: most severe first, numbered `G1`, `G2`, and so on. A finding with no single line gives the files and says `design-level`. A deleted line gives the base line and says `deleted`. Write `Rule:` when the finding rests on a rule, and `Trigger and consequence:` when it rests on behaviour. Write both when both apply. With no findings, write `No findings.` and keep the coverage section, so the result is read as clean only within that coverage.
- **Verdict**: the last section. `REQUEST_CHANGES` when any finding is critical or major, otherwise `APPROVE`. An `APPROVE` summary names the limits and areas not reviewed.

## Handing on

The findings are already in the shape the other review skills take: file and line, claim, trigger, severity in `critical`, `major`, or `minor`, and source. Just above the verdict, in one line, name the next steps that apply, so the verdict stays last:

- `review-cross-check` checks the findings against a pull request's existing review comments.
- `review-post` posts them to the pull request as a comment review, against the reviewed head commit.
- `review-fix` fixes them.

Do not run any of these unless the user asks.
