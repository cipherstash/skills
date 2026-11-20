# Output format

Read this in step 8. The review's output goes to the user in the conversation. It is not written to the repository or posted anywhere.

Use this shape. Keep every section, even when it is empty, so a reader can see what the review covered.

````markdown
# Go review: <target as given>

Reviewed `<base short SHA>`..`<head short SHA>` (full: `<base SHA>`..`<head SHA>`) in `<repository path or PR URL>`
Go version: 1.22 (`go.mod`)
Source: golang-review · <model ID, or unknown> · host <Claude Code, Codex, or unknown>
Skills: `golang-review`, `golang-practices`

## Checks

| Check | Scope | Outcome |
| --- | --- | --- |
| `go vet` | `./orders` | passed |
| `go test -race -count=1 -timeout 5m` | `./orders` | failed: `WARNING: DATA RACE`, write at `orders/orders.go:43` reached through `orders/orders.go:35` |

## Coverage and limits

- Areas reviewed: error handling, concurrency safety.
- Areas not reviewed: correctness and edge cases, testing and coverage, naming and style, security, performance, dependency management, documentation, breaking changes (not yet covered by golang-review).
- References read: golang-practices `references/error-handling.md`, `references/concurrency.md`.
- Limits: none.

## Findings

### G1 · major · `orders/orders.go:34` · decode error dropped

- Area: error handling
- Cause: the change calls `json.Unmarshal` as a statement, dropping its error. The base returned it.
- Trigger and consequence: a record that does not decode, such as `{"sku":"B2","quantity":"one"}`, is still counted as a line, with zero quantity and price, and `Summarise` returns a nil error.
- Rule: golang-practices error handling, "Check every returned error."
- Evidence: read at `orders/orders.go:34`. `go vet` does not report it.
- Fix: return each goroutine's error to `Summarise` and wrap it with the record's index.
- Source: golang-review · <model ID>

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
