# Error handling

Returning, wrapping, matching and reporting errors, and the few places a panic is the right tool.

The examples target Go 1.22, the `go` line in [`examples/go.mod`](../examples/go.mod). `errors.Is`, `errors.As`, and `%w` need Go 1.13 or later. `errors.Join`, and more than one `%w` in one `fmt.Errorf`, need Go 1.20 or later. Each example is quoted from the examples module, where tests check the behaviour the text describes.

## Contents

- [Rules](#rules)
- [Wrap errors with context](#wrap-errors-with-context)
- [Match wrapped errors with errors.Is and errors.As](#match-wrapped-errors-with-errorsis-and-errorsas)
- [Report several errors at once](#report-several-errors-at-once)
- [Never ignore an error silently](#never-ignore-an-error-silently)
- [Return a nil error as a literal nil](#return-a-nil-error-as-a-literal-nil)
- [Panic only for programmer errors](#panic-only-for-programmer-errors)

## Rules

- Check every returned error. Handle it, return it with context, or, rarely, ignore it explicitly with a comment that says why.
- Add context when you return an error: what this function was doing and the key values involved, followed by `%w` and the error.
- Handle an error once. Either return it or deal with it (log it, retry, use a fallback). Logging and then returning it reports the same failure twice.
- Match errors with `errors.Is` and `errors.As`. Both see through wrapping. Comparing with `==` or a type assertion on the error misses a wrapped error.
- Start error strings in lower case, unless they begin with a proper noun or acronym, and end them without punctuation. Leave out "failed to" and "error:" prefixes. Error strings are joined into longer messages, and these words only add noise there.
- Return `nil` itself for "no error", never a nil pointer of a concrete error type.
- Return an error for anything that can go wrong at run time. Panic only for programmer errors.

## Wrap errors with context

Each layer says what it was doing and passes the cause on with `%w`. The final message reads as a chain from the outermost operation to the root cause: `build greeting: user 7: not found`.

From [`examples/errorhandling/wrap.go`](../examples/errorhandling/wrap.go):

```go
// ErrNotFound is returned, wrapped, when a lookup finds nothing. Match it
// with errors.Is.
var ErrNotFound = errors.New("not found")

// Store is an in-memory user directory.
type Store struct {
	users map[int]string
}

// NewStore returns a Store holding users, keyed by ID.
func NewStore(users map[int]string) *Store {
	return &Store{users: users}
}

// Lookup returns the name of user id, or an error wrapping ErrNotFound.
func (s *Store) Lookup(id int) (string, error) {
	name, ok := s.users[id]
	if !ok {
		return "", fmt.Errorf("user %d: %w", id, ErrNotFound)
	}
	return name, nil
}

// Greeting returns a greeting for user id.
func Greeting(s *Store, id int) (string, error) {
	name, err := s.Lookup(id)
	if err != nil {
		return "", fmt.Errorf("build greeting: %w", err)
	}
	return "Hello, " + name, nil
}
```

How to choose the context:

- Name the operation and the values the reader needs to find the failing case: an ID, a key, a file name. Leave out values the wrapped error already contains. Errors from `*os.File` methods are `*fs.PathError` values that already name the operation and the path, so wrapping one with the path again repeats it. [`WriteLines`](#never-ignore-an-error-silently) shows this.
- Use `%w` when callers may need to match the cause. Use `%v` when callers must not depend on the cause, such as a driver error behind a storage interface. `%v` keeps the text and drops the error chain.
- Return the error unwrapped when this layer has nothing to add, such as a thin helper that the caller already names.

## Match wrapped errors with errors.Is and errors.As

Define a sentinel error (`var ErrNotFound = errors.New(...)`) when callers only need to know which failure happened. Define an error type when they need its details. Export either one only when callers are meant to match it, because it then becomes part of the API.

`errors.Is` walks the chain of wrapped errors looking for a value. `errors.As` walks it looking for a type. Pass it a pointer to a variable of that type. On a match, it sets the variable.

From [`examples/errorhandling/validation.go`](../examples/errorhandling/validation.go):

```go
// ValidationError reports an invalid field. Match it with errors.As.
type ValidationError struct {
	Field   string
	Problem string
}

func (e *ValidationError) Error() string {
	return e.Field + ": " + e.Problem
}

// ParsePort parses s as a TCP port number.
func ParsePort(s string) (int, error) {
	n, err := strconv.Atoi(s)
	if err != nil {
		return 0, fmt.Errorf("parse port: %w", err)
	}
	if err := CheckPort(n); err != nil {
		return 0, err
	}
	return n, nil
}

// CheckPort reports whether port is a usable TCP port number.
func CheckPort(port int) error {
	if port < 1 || port > 65535 {
		return &ValidationError{Field: "port", Problem: "must be between 1 and 65535"}
	}
	return nil
}
```

A test from the module shows both matches, and why `==` fails once an error is wrapped:

From [`examples/errorhandling/errorhandling_test.go`](../examples/errorhandling/errorhandling_test.go):

```go
func TestGreetingWrapsNotFoundWithContext(t *testing.T) {
	store := errorhandling.NewStore(map[int]string{1: "Ada"})

	got, err := errorhandling.Greeting(store, 1)
	if err != nil || got != "Hello, Ada" {
		t.Fatalf("Greeting(1) = %q, %v; want %q, nil", got, err, "Hello, Ada")
	}

	_, err = errorhandling.Greeting(store, 7)
	if want := "build greeting: user 7: not found"; err == nil || err.Error() != want {
		t.Fatalf("Greeting(7) error = %v, want %q", err, want)
	}
	if !errors.Is(err, errorhandling.ErrNotFound) {
		t.Fatalf("errors.Is(%v, ErrNotFound) = false, want true", err)
	}
	if err == errorhandling.ErrNotFound { // == compares identity and does not unwrap
		t.Fatal("a wrapped error compared equal to the sentinel; == should not see through wrapping")
	}
}
```

Standard library errors work the same way: `ParsePort` wraps the `*strconv.NumError` from `strconv.Atoi`, so `errors.Is(err, strconv.ErrSyntax)` still reports a non-numeric port.

## Report several errors at once

To report every problem rather than the first, collect the errors and join them. `errors.Join` returns `nil` when given no non-nil errors, and `errors.Is` and `errors.As` search every joined error.

From [`examples/errorhandling/validation.go`](../examples/errorhandling/validation.go):

```go
// ValidateServer reports every problem with host and port, not only the first.
func ValidateServer(host string, port int) error {
	var errs []error
	if host == "" {
		errs = append(errs, &ValidationError{Field: "host", Problem: "is required"})
	}
	if err := CheckPort(port); err != nil {
		errs = append(errs, err)
	}
	return errors.Join(errs...) // nil when errs is empty
}
```

## Never ignore an error silently

An unchecked error hides the failure and lets the program carry on with bad state. Check it, even from calls that rarely fail.

`Close` on something you wrote to is a common case. A file system may report a write failure only on close. So `defer f.Close()` on a written file can lose data without a word. Check the error from `Close`, and use `errors.Join` so a write error and a close error are both reported. The result `err` is named so that the deferred function can set it.

From [`examples/errorhandling/files.go`](../examples/errorhandling/files.go):

```go
// WriteAll writes each line to w and then closes w. It reports a failed
// Close as well as a failed write: for a file, Close can be where a write
// error first shows up.
func WriteAll(w io.WriteCloser, lines []string) (err error) {
	defer func() {
		if cerr := w.Close(); cerr != nil {
			err = errors.Join(err, fmt.Errorf("close: %w", cerr))
		}
	}()
	for _, line := range lines {
		if _, err = fmt.Fprintln(w, line); err != nil {
			return fmt.Errorf("write line: %w", err)
		}
	}
	return nil
}

// WriteLines creates or truncates the file at path and writes lines to it.
func WriteLines(path string, lines []string) error {
	// Errors from *os.File methods are *fs.PathError values, which already
	// name the operation and the path, so the wrapping adds only what this
	// function was doing.
	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("write lines: %w", err)
	}
	if err := WriteAll(f, lines); err != nil {
		return fmt.Errorf("write lines: %w", err)
	}
	return nil
}
```

`defer resp.Body.Close()` on something you only read is accepted practice. The data has already arrived, so there is nothing useful to do with the error. The `Fetch` example in the concurrency reference does this, with a comment saying why.

When ignoring an error is right, make it visible. Assign it to `_` and add a comment saying why it cannot matter, for example `_ = os.Remove(tmp) // best effort: tmp is in a directory cleared at start-up`. A bare call that drops the error looks like a mistake to the reader and to linters such as `errcheck`.

## Return a nil error as a literal nil

An interface value is `nil` only when it has neither a type nor a value. A nil `*ValidationError` returned as an `error` has a type. So the caller sees a non-nil error, and `err != nil` is always true.

From [`examples/errorhandling/validation.go`](../examples/errorhandling/validation.go):

```go
// CheckPortTypedNil shows a mistake: it returns a nil *ValidationError as an
// error, and an interface holding a typed nil pointer is not nil. Callers
// see a failure for every port. Return the literal nil instead, as CheckPort
// does.
func CheckPortTypedNil(port int) error {
	var verr *ValidationError
	if port < 1 || port > 65535 {
		verr = &ValidationError{Field: "port", Problem: "must be between 1 and 65535"}
	}
	return verr // wrong: never a nil error
}
```

`CheckPort`, above, returns the literal `nil` instead. To avoid the trap, declare a variable you will return as `error`, not as a concrete error type.

## Panic only for programmer errors

A panic stops the goroutine and, unless something recovers it, the whole program. Return an error for anything a caller could reasonably handle: bad input, a missing file, a failed request, a timeout. Panic only when continuing would hide a bug:

- An invariant the program itself guarantees has been broken: an impossible `switch` case, a nil dependency that the constructor requires.
- A `Must` helper for values fixed in the source, checked once at start-up, like `regexp.MustCompile`. Keep a non-panicking version beside it for values that arrive at run time.

From [`examples/errorhandling/panics.go`](../examples/errorhandling/panics.go):

```go
// MustParsePort is ParsePort for values fixed in the source, such as a
// package-level default. It panics if s is not a valid port, because that is
// a bug in the program, not a runtime condition to handle.
func MustParsePort(s string) int {
	port, err := ParsePort(s)
	if err != nil {
		panic(fmt.Sprintf("MustParsePort(%q): %v", s, err))
	}
	return port
}

// defaultPort is checked once, at program start.
var defaultPort = MustParsePort("8080")

// DefaultPort returns the port used when none is configured.
func DefaultPort() int { return defaultPort }
```

A library does not let a panic escape its exported functions for a failure the caller could handle; it returns an error.

Recover only at a boundary that keeps a long-running process alive, such as the top of a worker that runs third-party tasks. There, turn the panic into an error with its stack. `net/http` already recovers a panic in each handler. `recover` only catches a panic in its own goroutine, so a goroutine the task starts needs its own boundary.

From [`examples/errorhandling/panics.go`](../examples/errorhandling/panics.go):

```go
// PanicError is a panic recovered by RunSafely.
type PanicError struct {
	Value any    // the value passed to panic
	Stack []byte // the panicking goroutine's stack
}

func (e *PanicError) Error() string {
	return fmt.Sprintf("panic: %v", e.Value)
}

// RunSafely calls fn and returns its error. If fn panics, RunSafely recovers
// and returns a *PanicError instead, so one failing task does not crash a
// long-running process. It only catches panics in the goroutine that calls
// it: a goroutine fn starts needs its own recover.
func RunSafely(fn func() error) (err error) {
	defer func() {
		if r := recover(); r != nil {
			err = &PanicError{Value: r, Stack: debug.Stack()}
		}
	}()
	return fn()
}
```
