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
| `go test -race -count=1 -timeout 5m -coverprofile=<tmp>/cover.out` | `./orders` | failed: `WARNING: DATA RACE`, write at `orders/orders.go:43` reached through `orders/orders.go:35` |
| `go tool cover -func` | `./orders` | 95.8% of statements; untested: `Merge` (`orders/report.go:13`) |
| `gofmt -l` | changed `.go` files | failed: `orders/units.go` |
| `go mod tidy -diff` | `.` | failed: removes `require example.com/pricing v0.0.0` |
| `go doc -all` at base and head | `./orders` | 1 removed, 6 added; see API changes |
| `staticcheck`, `gosec`, `apidiff` | | not run: not installed |
| `govulncheck` | `./...` | not run: needs the vulnerability database over the network |

## API changes

- Removed: `func (s Summary) Empty() bool` (`orders/orders.go:44` at the base).
- Added: `DefaultCurrency`, `Summary.AverageCents`, `Summary.Merge`, `SKUs`, `LinesQuery`, `Summary.UnitsPerLine`.
- Version: v0 (no module path suffix, no tags). Name the removal in the release notes and bump the minor version. At v1 or later it would need a new major version.

## Coverage and limits

- Areas reviewed: all ten, in priority order.
- Areas not reviewed: none.
- References read: golang-practices `references/error-handling.md`, `references/interfaces.md`, `references/testing.md`, `references/concurrency.md`, `references/project-structure.md`, `references/security.md`, `references/performance.md`, `references/dependencies.md`.
- Limits: `govulncheck` not run, so known vulnerabilities were not checked; `staticcheck`, `gosec`, and `apidiff` not installed.

## Findings

### G1 · critical · `orders/query.go:6` · SQL built from customer input

- Area: security
- Cause: `LinesQuery` concatenates `sku`, which its doc comment says the customer typed, into the SQL text.
- Trigger and consequence: the SKU `x' OR '1'='1` selects every order line, and other input can change the statement further.
- Rule: golang-practices security, "Build SQL with placeholders and pass values as arguments."
- Evidence: read at `orders/query.go:6`. `gosec` not installed.
- Fix: return the query with a placeholder and pass `sku` to `QueryContext` as an argument.
- Source: golang-review · <model ID>

### G2 · major · `orders/orders.go:34` · decode error dropped

- Area: error handling
- Cause: the change calls `json.Unmarshal` as a statement, dropping its error. The base returned it.
- Trigger and consequence: a record that does not decode, such as `{"sku":"B2","quantity":"one"}`, is still counted as a line, with zero quantity and price, and `Summarise` returns a nil error.
- Rule: golang-practices error handling, "Check every returned error."
- Evidence: read at `orders/orders.go:34`. `go vet` does not report it.
- Fix: return each goroutine's error to `Summarise` and wrap it with the record's index.
- Source: golang-review · <model ID>

<further findings, most severe first>

## Verdict

REQUEST_CHANGES: <one to three sentences: what blocks the change, and any limit the reader must know.>
````

## Fields

- **Reviewed**: full SHAs for base and head. For uncommitted changes, write `HEAD <SHA> plus uncommitted changes`. A snapshot has no commit for `review-post` to post against, so say the user must commit before posting.
- **Go version**: one line per module when the change touches several. Write `1.16 (no go line)` where the module has none.
- **Checks**: one row per check, with the exact command and scope. The outcome is `passed`, `failed: <evidence>`, or `not run: <reason>`, as `checks.md` defines them. A check run without `-race`, because the race detector was unavailable, is its own row. The coverage row gives the total and every function in a changed file at 0.0%, or `not run` with the reason when the tests did not run.
- **API changes**: every removed, renamed, or changed exported declaration, the additions in one line, and the version note, as `step-breaking-changes.md` describes. Write `None.` when the exported API is unchanged, and `not compared: <reason>` when the review could not compare it, which is also a limit. Leave the section out only when breaking changes are not in scope at the user's request.
- **Coverage and limits**: every area is listed once, as reviewed or not reviewed with the reason: left out at the user's request, or cut for scope. List the golang-practices references read. If the skill could not be loaded, write `golang-practices not loaded:` and the references not read under limits. Every check not run is a limit, as is any change to the user's tree found in step 8.
- **Findings**: most severe first, numbered `G1`, `G2`, and so on. A finding with no single line gives the files and says `design-level`. A deleted line gives the base line and says `deleted`. Write `Rule:` when the finding rests on a rule, and `Trigger and consequence:` when it rests on behaviour. Write both when both apply. With no findings, write `No findings.` and keep the coverage section, so the result is read as clean only within that coverage.
- **Verdict**: the last section. `REQUEST_CHANGES` when any finding is critical or major, otherwise `APPROVE`. An `APPROVE` summary names the limits and areas not reviewed.

## Handing on

The findings are already in the shape the other review skills take: file and line, claim, trigger, severity in `critical`, `major`, or `minor`, and source. Just above the verdict, in one line, name the next steps that apply, so the verdict stays last:

- `review-cross-check` checks the findings against a pull request's existing review comments.
- `review-post` posts them to the pull request as a comment review, against the reviewed head commit.
- `review-fix` fixes them.

Do not run any of these unless the user asks.
