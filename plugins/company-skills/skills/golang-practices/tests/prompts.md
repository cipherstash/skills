# Behavior cases

This is a background convention skill: it is applied while the agent writes Go, not invoked by name. `golang-review` also loads it to read its references during a review.

## Should activate

- "Add a worker pool to `ingest/` that processes uploads four at a time." (in a Go module)
- "This handler swallows the error from `db.Exec`; make it return it properly." (in a Go service)
- "Make this Go function time out if the upstream API hangs."
- "Add a generic `Set` type to our Go utilities package."
- "Write table-driven tests for `ParseConfig` in `config.go`."
- "Our Go client fails against the staging server's self-signed certificate; make it connect." The agent trusts the staging CA rather than setting `InsecureSkipVerify`.
- "Bump `github.com/jackc/pgx/v5` to the latest patch release." (in a Go module)
- "The importer sometimes leaks goroutines; can you sort it out?" in a Go repository, with no file named. The agent asks which code path to look at, or finds the goroutines the importer starts, before changing code.

## Should not activate

- "Review this Go pull request for concurrency bugs." — reviewing Go is `golang-review`'s job, though it loads this skill's references.
- "Add a retry with backoff to this TypeScript fetch wrapper."
- "Fix the error handling in this Rust crate's client." — Rust conventions are in `rust-sdk-dx`.
- "Write a Python script that calls our Go service's HTTP API."

## Expected behavior

- The agent reads the `go` line in `go.mod` before applying version-sensitive advice. For example, it copies a loop variable for a goroutine only below Go 1.22.
- The agent reads `references/concurrency.md` before writing goroutines, channels, or `sync` code, and `references/error-handling.md` before writing error handling. Likewise it reads `interfaces.md`, `generics.md`, `testing.md`, `project-structure.md`, `security.md`, `performance.md`, or `dependencies.md` before work in that area. It does not load references for areas the change does not touch.
- Every goroutine the agent writes has a way to stop and something that waits for it. The way to stop is a context, a closed input, or a stop method that is safe to call twice.
- Blocking calls take a `context.Context`. The code returns as soon as the work is done, not when a timeout expires.
- Errors are checked, wrapped with `%w` and context, and matched with `errors.Is` or `errors.As`. An ignored error has a comment saying why, and `_ =` unless it is a deferred `Close` on something only read.
- A panic is used only for a programmer error.
- Package, identifier, and receiver names follow the naming rules: `userID`, not `userId`; receiver `s`, not `self`.
- Tests are table-driven with named subtests. They copy the loop variable for parallel subtests only below Go 1.22, and stop with `t.Fatalf` before indexing a slice that may be empty.
- The agent never turns off TLS verification, writes a secret into source, or builds SQL by concatenating input.
- A dependency update changes one module to a chosen version, and runs `go mod tidy` and the tests. It does not run `go get -u ./...`.
- The agent runs `gofmt`, `go vet ./...`, and `go test -race ./...`, or says which it could not run.
- The agent does not invent packages, helpers, or repository paths that are not in the user's codebase.
- The agent adds a third-party dependency, such as `errgroup`, only when it says so.
