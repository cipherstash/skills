# Behavior cases

This is a background convention skill: it is applied while the agent writes Go, not invoked by name. `golang-review` also loads it to read its references during a review.

## Should activate

- "Add a worker pool to `ingest/` that processes uploads four at a time." (in a Go module)
- "This handler swallows the error from `db.Exec`; make it return it properly." (in a Go service)
- "Make this Go function time out if the upstream API hangs."
- "The importer sometimes leaks goroutines; can you sort it out?" in a Go repository, with no file named. The agent asks which code path to look at, or finds the goroutines the importer starts, before changing code.

## Should not activate

- "Review this Go pull request for concurrency bugs." — reviewing Go is `golang-review`'s job, though it loads this skill's references.
- "Add a retry with backoff to this TypeScript fetch wrapper."
- "Fix the error handling in this Rust crate's client." — Rust conventions are in `rust-sdk-dx`.
- "Write a Python script that calls our Go service's HTTP API."

## Expected behavior

- The agent reads the `go` line in `go.mod` before applying version-sensitive advice. For example, it copies a loop variable for a goroutine only below Go 1.22.
- The agent reads `references/concurrency.md` before writing goroutines, channels, or `sync` code. It reads `references/error-handling.md` before writing error handling. It does not load references for areas the change does not touch.
- Every goroutine the agent writes has a way to stop and something that waits for it. The way to stop is a context, a closed input, or a stop method that is safe to call twice.
- Blocking calls take a `context.Context`. The code returns as soon as the work is done, not when a timeout expires.
- Errors are checked, wrapped with `%w` and context, and matched with `errors.Is` or `errors.As`. An ignored error has a comment saying why, and `_ =` unless it is a deferred `Close` on something only read.
- A panic is used only for a programmer error.
- The agent runs `gofmt`, `go vet ./...`, and `go test -race ./...`, or says which it could not run.
- The agent does not invent packages, helpers, or repository paths that are not in the user's codebase.
- The agent adds a third-party dependency, such as `errgroup`, only when it says so.
