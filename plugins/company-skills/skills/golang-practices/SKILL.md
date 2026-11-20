---
name: golang-practices
description: Applies CipherStash conventions for writing Go — error wrapping and matching, goroutine lifetimes and cancellation, context on blocking calls, channels, and sync primitives. Use when writing or changing Go code (.go files, Go tests, go.mod), such as adding a goroutine, worker pool, error type, or error handling. Does not apply to other languages, or to reviewing a Go change, which golang-review does using this skill's references.
user-invocable: false
---

# Go practices

Rules for writing Go. Apply them to every Go change, and read the reference for each area the change touches before writing code in it.

## Rules

### General

- Read the `go` line in the module's `go.mod` before applying a version-sensitive rule. The references say which rules depend on it.
- If the repository's own guidance differs from these rules, follow the repository. Say that you did.
- Format with `gofmt`, run `go vet ./...`, and run the tests with `go test -race ./...` before calling a change done.

### Errors

- Check every returned error. Handle it or return it with context. Ignore one only on purpose, with a comment saying why it cannot matter: `_ =` for most calls, or a deferred `Close` on something you only read.
- Wrap with `fmt.Errorf("what this function was doing: %w", err)`, naming the key values. Leave out what the wrapped error already says.
- Handle an error once: return it, or log it and carry on, not both.
- Match with `errors.Is` and `errors.As`. A `==` comparison or a type assertion misses a wrapped error.
- Return the literal `nil` for no error, never a nil pointer of a concrete error type.
- Error strings start in lower case, unless they begin with a proper noun or acronym, and have no trailing punctuation.
- Return errors for run-time failures. Panic only for programmer errors, such as a broken invariant or a `Must` helper on a value fixed in the source.

### Concurrency

- Start a goroutine only when you know how it stops and what waits for it.
- A channel send or receive that could wait forever also selects on `ctx.Done()` or another stop signal. Ranging over a channel is fine when its sender is certain to close it.
- A function that blocks takes a `context.Context` as its first parameter and returns when it ends. Pass the context to the blocking call itself.
- Return as soon as the work is done. A result that arrives only when a timeout expires is a bug.
- Only the sender closes a channel, once. Stop and shutdown methods are safe to call more than once.
- Errors from goroutines reach whoever waits for them.

## References

Read the reference for each area the change touches. Each one states the Go version its examples target. Its examples are quoted from the [examples module](examples/go.mod), where they compile and pass their tests.

| Read | When the change involves |
| --- | --- |
| [references/error-handling.md](references/error-handling.md) | Returning, wrapping, matching or joining errors, sentinel errors and error types, `Close` errors, `panic` and `recover` |
| [references/concurrency.md](references/concurrency.md) | Goroutines, channels, `select`, `context` cancellation and timeouts, worker pools, pipelines, mutexes, `sync.Once`, semaphores, rate limits |
