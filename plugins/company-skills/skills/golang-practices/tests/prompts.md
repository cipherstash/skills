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
- "Add a decoder that runs a WebAssembly build of a C library through wazero, and call it from several HTTP handlers." The agent serialises calls or uses one instance per caller. It copies bytes out of `Memory().Read`.
- "We set `WithCloseOnContextDone(true)` and added an mmap-backed memory allocator. What else do we need?" The agent raises the release-after-cancel bug and the host-side defence, with the once-only free.
- "Our Go service that uses wazero returns `module closed with context deadline exceeded` after one slow request." The agent asks for the runtime config and how modules are shared before it changes code.

## Should not activate

- "Review this Go pull request for concurrency bugs." — reviewing Go is `golang-review`'s job, though it loads this skill's references.
- "Add a retry with backoff to this TypeScript fetch wrapper."
- "Fix the error handling in this Rust crate's client." — Rust conventions are in `rust-sdk-dx`.
- "Write a Python script that calls our Go service's HTTP API."
- "Write a Rust function that exports `alloc` and `free` for a WebAssembly guest." The guest side is out of scope, even when a Go host runs it with wazero.

## Expected behavior

- The agent reads the `go` line in `go.mod` before applying version-sensitive advice. For example, it copies a loop variable for a goroutine only below Go 1.22.
- The agent reads `references/concurrency.md` before writing goroutines, channels, or `sync` code, and `references/error-handling.md` before writing error handling. Likewise it reads `interfaces.md`, `generics.md`, `testing.md`, `project-structure.md`, `security.md`, `performance.md`, `dependencies.md`, or `wazero.md` before work in that area. It does not load references for areas the change does not touch.
- Every goroutine the agent writes has a way to stop and something that waits for it. The way to stop is a context, a closed input, or a stop method that is safe to call twice.
- Blocking calls take a `context.Context`. The code returns as soon as the work is done, not when a timeout expires.
- Errors are checked, wrapped with `%w` and context, and matched with `errors.Is` or `errors.As`. An ignored error has a comment saying why, and `_ =` unless it is a deferred `Close` on something only read.
- A panic is used only for a programmer error.
- Package, identifier, and receiver names follow the naming rules: `userID`, not `userId`; receiver `s`, not `self`.
- Tests are table-driven with named subtests. They copy the loop variable for parallel subtests only below Go 1.22, and stop with `t.Fatalf` before indexing a slice that may be empty.
- The agent never turns off TLS verification, writes a secret into source, or builds SQL by concatenating input.
- A dependency update changes one module to a chosen version, and runs `go mod tidy` and the tests. It does not run `go get -u ./...`.
- The agent formats with `gofumpt`. The agent may run any suite tool from `references/checks.md` that helps it get the change right. CI stays the gate.
- The agent does not invent packages, helpers, or repository paths that are not in the user's codebase.
- A wazero host function the agent writes returns an expected failure through the guest's error path. It does not panic for one.
- A wazero module config for production sets `WithRandSource(rand.Reader)` and the real clocks. The deterministic defaults stay only in tests that say why.
- With a custom wazero allocator, the agent frees host-staged buffers before the allocator's `Exit`. It checks `IsClosed` before `Enter` and before any call after `Exit`. It does not guard a free inside that bracket with `IsClosed`.
- The agent states that the fix for wazero/wazero#2558 was open when the reference was written. It checks the state before it recommends a wazero version.
- The agent gives the wazero Go module path as `github.com/tetratelabs/wazero`, not `github.com/wazero/wazero`.
- The agent adds a third-party dependency, such as `errgroup`, only when it says so.
