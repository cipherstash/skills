---
name: golang-practices
description: Applies CipherStash conventions for writing Go — error handling, concurrency and context, naming, interfaces, generics, tests, project layout and modules, security, performance, dependencies, and embedding the wazero WebAssembly runtime. Use when writing or changing Go code (.go files, Go tests, go.mod), such as adding a goroutine, error type, interface, generic function, test, package, dependency, or wazero host function. Does not apply to other languages, or to reviewing a Go change, which golang-review does using this skill's references.
user-invocable: false
---

# Go practices

Rules for writing Go. Apply them to every Go change, and read the reference for each area the change touches before writing code in it.

## Rules

### General

- Read the `go` line in the module's `go.mod` before applying a version-sensitive rule. The references say which rules depend on it.
- If the repository's own guidance differs from these rules, follow the repository. Say that you did.
- The Go check suite in [references/checks.md](references/checks.md) lists the checks CI runs on every pull request. CI is the gate. Run any suite tool that helps you get a change right.
- Format with `gofumpt`, through the suite.

### Errors

- Check every returned error. Handle it or return it with context. Ignore one only on purpose, with a comment saying why it cannot matter: `_ =` for most calls, or a deferred `Close` on something you only read.
- Wrap with `fmt.Errorf("what this function was doing: %w", err)`, naming the key values. Leave out what the wrapped error already says.
- Return a sentinel that an interface's contract names, such as `io.EOF` from `Read`, unwrapped, because callers such as `io.ReadAll` compare it with `==`. In your own code, match it with `errors.Is`. A thin `io.Reader` or `io.Writer` that wraps another returns the inner error unchanged.
- Handle an error once: return it, or log it and carry on, not both.
- Match with `errors.Is` and `errors.As`. A `==` comparison or a type assertion misses a wrapped error.
- Return the literal `nil` for no error, never a nil pointer of a concrete error type.
- Return a usable value or an error, not both. On error, return the zero value or `nil` with it. The exception is a partial result the contract documents, such as the `n` bytes that `io.Reader` and `io.Writer` return with an error.
- Error strings start in lower case, unless they begin with a proper noun or acronym, and have no trailing punctuation.
- Return errors for run-time failures. Panic only for programmer errors, such as a broken invariant or a `Must` helper on a value fixed in the source.

### Concurrency

- Start a goroutine only when you know how it stops and what waits for it.
- A channel send or receive that could wait forever also selects on `ctx.Done()` or another stop signal. Ranging over a channel is fine when its sender is certain to close it.
- A function that blocks takes a `context.Context` as its first parameter and returns when it ends. Pass the context to the blocking call itself.
- Return as soon as the work is done. A result that arrives only when a timeout expires is a bug.
- Only the sender closes a channel, once. Stop and shutdown methods are safe to call more than once.
- Errors from goroutines reach whoever waits for them.

### Naming

- Package names are short, lower case, one word, and say what the package provides. No `util`, `common`, or `models`. Exported names do not repeat the package name: `user.Service`, not `user.UserService`.
- Initialisms keep one case: `ID`, `URL`, `HTTP`, as in `userID` and `ServeHTTP`.
- A receiver is one or two letters from its type, and the same on every method. Never use `this` or `self`.
- Name a one-method interface for what it does: usually the method plus `-er`, as in `Reader` and `Flusher`, or the role when that says more, as in `http.Handler` and `Mailer`. No `I` prefix or `Interface` suffix.
- Document every exported name with a comment that starts with the name.

### Interfaces and generics

- Define an interface where it is used, with only the methods used. Accept interfaces, return concrete types.
- Use the two-value type assertion, `v, ok := x.(T)`, unless a failure is a bug.
- Add a type parameter when the same code would be copied for several types. Check `slices`, `maps`, and `cmp` first.
- Use `cmp.Ordered`, not a `constraints` package. Use the built-in `min` and `max`, and never shadow them.

### Testing

- Write table-driven tests with named subtests. Stop with `t.Fatalf` before a step that would panic, such as indexing a slice that may be empty.
- Copy the loop variable for a parallel subtest (`tt := tt`) only when the `go` line is below 1.22.
- Use hand-written fakes over mocking libraries, unless the project already generates mocks with `go.uber.org/mock`. Use `//go:build` lines, never `// +build`.

### Security

- Never set `InsecureSkipVerify` outside tests, put a secret in source, or log a secret.
- Build SQL with placeholders. Never concatenate input into a query, or format it in.
- Check paths, sizes, and other input from outside the process. Use `html/template` for HTML and `crypto/rand` for secrets.
- Run `gosec` and `govulncheck` as the check suite sets them up. See [references/checks.md](references/checks.md).

### Performance

- Measure before optimising, with benchmarks (`-benchmem`) and profiles.
- Size slices and maps when the length is known. Build strings with `strings.Builder`. Keep allocation and one-off setup out of hot loops.

### Modules and dependencies

- Prefer the standard library. Run `go mod tidy` after changing imports, and commit `go.mod` and `go.sum` together.
- Update one dependency at a time to a chosen version, and test after each. Do not run `go get -u ./...` as a routine step.

### wazero

- A host function returns an expected failure to the guest. It never panics for one. Replace an instance after a trap.
- Call into one module from one goroutine at a time, or give each goroutine its own instance. `Close` takes the same lock as the calls.
- Copy bytes out of a `Memory().Read` view before anything else runs on the instance.
- In production, set `WithRandSource(rand.Reader)` and the real clocks on the module config.
- With `WithCloseOnContextDone(true)`, a cancel closes the module. Build a new instance for the next call.
- A custom `MemoryAllocator` must follow sections 9 and 10 of the wazero reference: when to free the memory, and the cleanup order after a cancel.

## References

Read the reference for each area the change touches. Each one states the Go version its examples target. Its examples are quoted from the [examples module](examples/go.mod), where they compile and pass their tests.

| Read | When the change involves |
| --- | --- |
| [references/error-handling.md](references/error-handling.md) | Returning, wrapping, matching or joining errors, sentinel errors and error types, `Close` errors, `panic` and `recover` |
| [references/concurrency.md](references/concurrency.md) | Goroutines, channels, `select`, `context` cancellation and timeouts, worker pools, pipelines, mutexes, `sync.Once`, semaphores, rate limits |
| [references/interfaces.md](references/interfaces.md) | Defining or implementing an interface, `io.Reader` and `io.Writer`, embedding, functional options, type assertions and switches, pointer or value receivers |
| [references/generics.md](references/generics.md) | Type parameters, constraints and unions, generic types, generic channel stages |
| [references/testing.md](references/testing.md) | Writing or changing tests: table tests, parallel subtests, fakes, golden files, fuzzing, the race detector, build-tagged tests, examples, coverage |
| [references/project-structure.md](references/project-structure.md) | Adding a package or binary, naming packages and identifiers, `internal/`, `go.mod` and workspaces, build constraints, configuration, build information, `go generate`, Dockerfiles |
| [references/security.md](references/security.md) | TLS clients or servers, secrets and credentials, SQL, file paths, request bodies, HTML, shell commands, tokens and random values, security linters |
| [references/performance.md](references/performance.md) | Code on a hot path, slice and map sizing, string building, allocation, benchmarks, profiling |
| [references/dependencies.md](references/dependencies.md) | Adding, updating or removing a module, `go mod tidy`, vulnerability checks, outdated dependencies, major versions, raising the `go` line |
| [references/checks.md](references/checks.md) | The checks CI runs on every pull request: golangci-lint, govulncheck, semgrep, race-enabled tests with coverage, Fuzz targets for code that parses untrusted input, and their pinned versions |
| [references/wazero.md](references/wazero.md) | Code that imports `github.com/tetratelabs/wazero`: host functions, sharing or closing a module, context cancellation, reading and freeing guest memory, the module config, custom memory allocators |
