# Output format

Read this in step 8. The review's output goes to the user in the conversation. It is not written to the repository or posted anywhere.

Use this shape. Keep every section, even when it is empty, so a reader can see what the review covered.

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
| `go test -race -count=1 -timeout 5m` | `./mailer` | failed: `WARNING: DATA RACE`, write at `mailer/queue.go:58` reached through `mailer/queue.go:71` |

## Coverage and limits

- Areas reviewed: error handling, concurrency safety.
- Areas not reviewed: correctness and edge cases, testing and coverage, naming and style, security, performance, dependency management, documentation, breaking changes (not yet covered by golang-review).
- References read: golang-practices `references/error-handling.md`, `references/concurrency.md`.
- Limits: none.

## Findings

### G1 · major · `mailer/queue.go:64` · send error logged and dropped

- Area: error handling
- Cause: the change replaces `return fmt.Errorf("send %s: %w", m.ID, err)` with a log line and `continue`, so `Flush` returns nil after a failed send. The base returned the error.
- Trigger and consequence: when the mail server refuses one message, `Flush` returns nil and `Worker.run` deletes the whole batch from the queue, so the refused message is never retried.
- Rule: golang-practices error handling, "Check every returned error."
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
- **Checks**: one row per check, with the exact command and scope. The outcome is `passed`, `failed: <evidence>`, or `not run: <reason>`, as `checks.md` defines them. A check run without `-race`, because the race detector was unavailable, is its own row.
- **Coverage and limits**: every area is listed once, as reviewed or not reviewed with the reason: not yet covered by golang-review, left out at the user's request, or cut for scope. List the golang-practices references read. If the skill could not be loaded, write `golang-practices not loaded: references/error-handling.md and references/concurrency.md not read` under limits. Every check not run is a limit, as is any change to the user's tree found in step 8.
- **Findings**: most severe first, numbered `G1`, `G2`, and so on. A finding with no single line gives the files and says `design-level`. A deleted line gives the base line and says `deleted`. Write `Rule:` when the finding rests on a rule, and `Trigger and consequence:` when it rests on behaviour. Write both when both apply. With no findings, write `No findings.` and keep the coverage section, so the result is read as clean only within that coverage.
- **Verdict**: the last section. `REQUEST_CHANGES` when any finding is critical or major, otherwise `APPROVE`. An `APPROVE` summary names the limits and areas not reviewed.

## Handing on

The findings are already in the shape the other review skills take: file and line, claim, trigger, severity in `critical`, `major`, or `minor`, and source. Just above the verdict, in one line, name the next steps that apply, so the verdict stays last:

- `review-cross-check` checks the findings against a pull request's existing review comments.
- `review-post` posts them to the pull request as a comment review, against the reviewed head commit.
- `review-fix` fixes them.

Do not run any of these unless the user asks.
