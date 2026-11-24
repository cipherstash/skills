# Testing

Table-driven tests, subtests, fakes, golden files, fuzzing, the race detector, tests behind build tags, and testable examples. Benchmarks are in `performance.md`.

The examples target Go 1.22, the `go` line in [`examples/go.mod`](../examples/go.mod). Fuzzing needs Go 1.18. The loop-variable rule depends on the module's Go version, as the text says. Each example is quoted from the examples module, where it runs under `go test -race`.

## Contents

- [Rules](#rules)
- [Table-driven tests](#table-driven-tests)
- [Parallel subtests and the loop variable](#parallel-subtests-and-the-loop-variable)
- [Helpers and clean-up](#helpers-and-clean-up)
- [Fakes instead of mocking libraries](#fakes-instead-of-mocking-libraries)
- [Golden files](#golden-files)
- [Fuzzing](#fuzzing)
- [The race detector](#the-race-detector)
- [Tests behind a build tag](#tests-behind-a-build-tag)
- [Testable examples](#testable-examples)
- [Coverage](#coverage)
- [Quick reference](#quick-reference)

## Rules

- Write table-driven tests with named cases and `t.Run`, so a failure names its case and `-run` can select it.
- Run the tests with the race detector. [checks.md](checks.md) gives the command CI runs. A data race is a bug even when the test passes.
- Use `t.Fatalf` when the rest of the test cannot run, such as before indexing a slice that may be empty. Use `t.Errorf` to report a failure and keep checking.
- Say what was wrong in the message: the call, what it returned, and what was wanted. `Reverse("ab") = "ab", want "ba"`.
- Mark helpers with `t.Helper()`, and use `t.Cleanup` and `t.TempDir` for clean-up.
- Check the errors a test's own calls return, including writes to fixtures and golden files.
- Prefer a small hand-written fake to a mocking library.
- Wait for a condition, not a fixed time. `time.Sleep` to wait for a server makes tests slow and still flaky.
- Put the build constraint for tagged tests above the `package` clause, as `//go:build integration`, followed by a blank line.
- A test that is missing, such as a Fuzz target or a doctest-style example, is not a defect in itself. Add one when it would catch a plausible regression. The exception: a function that parses or decodes untrusted input must have a Fuzz target, as [checks.md](checks.md) says.

## Table-driven tests

Each case is a struct with a name, the inputs, and the wanted result. Adding a case is one line.

From [`examples/textutil/textutil_test.go`](../examples/textutil/textutil_test.go):

```go
func TestReverse(t *testing.T) {
	tests := []struct {
		name string
		in   string
		want string
	}{
		{name: "empty", in: "", want: ""},
		{name: "one rune", in: "a", want: "a"},
		{name: "ascii", in: "hello", want: "olleh"},
		{name: "multi-byte runes", in: "héllo, 世界", want: "界世 ,olléh"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			// From Go 1.22 each iteration has its own tt, so the parallel
			// subtest sees the right case without a tt := tt copy.
			if got := textutil.Reverse(tt.in); got != tt.want {
				t.Errorf("Reverse(%q) = %q, want %q", tt.in, got, tt.want)
			}
		})
	}
}
```

The cases cover the empty input, one element, and the usual case. They also cover the input most likely to break the code: multi-byte UTF-8. A byte-wise reverse would corrupt it.

## Parallel subtests and the loop variable

`t.Parallel()` in a subtest lets cases run at the same time. The subtest's function runs after the loop moves on, so it must see the right `tt`:

- **Go 1.22 and later** (the `go` line in `go.mod` is `go 1.22` or higher): each loop iteration has its own `tt`. No copy is needed, as in `TestReverse` above.
- **Before Go 1.22**: all iterations share one `tt`, and parallel subtests may all see the last case. Add `tt := tt` as the first line of the loop body.

The rule follows the `go` line of the module being built, not the version of the installed toolchain. Remove `tt := tt` copies when a module moves to Go 1.22; they are harmless but no longer needed.

Do not use `t.Parallel()` in tests that change shared state, such as environment variables or package-level variables. `t.Setenv` refuses to run in a parallel test.

## Helpers and clean-up

`t.Helper()` makes a failure point at the caller's line instead of the helper's. `t.TempDir()` returns a directory that is removed when the test ends. `t.Cleanup(fn)` runs `fn` when the test ends, in reverse order of registration, even after `t.Fatal`.

From [`examples/textutil/helpers_test.go`](../examples/textutil/helpers_test.go):

```go
// writeFixture writes content to a file in a fresh temporary directory and
// returns its path. t.Helper makes a failure point at the caller's line, and
// t.TempDir removes the directory when the test ends.
func writeFixture(t *testing.T, name, content string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), name)
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("write fixture %s: %v", name, err)
	}
	return path
}
```

## Fakes instead of mocking libraries

The code under test takes a small interface, so a test can pass a hand-written fake. The fake records what it was asked to do. A field tells it to fail.

From [`examples/welcome/welcome.go`](../examples/welcome/welcome.go):

```go
// Sender sends a message to an address.
type Sender interface {
	Send(ctx context.Context, to, body string) error
}

// Welcome sends a welcome message to each address, stopping at the first
// failure.
func Welcome(ctx context.Context, s Sender, addrs []string) error {
	for _, to := range addrs {
		if err := s.Send(ctx, to, "Welcome!"); err != nil {
			return fmt.Errorf("welcome %s: %w", to, err)
		}
	}
	return nil
}
```

From [`examples/welcome/welcome_test.go`](../examples/welcome/welcome_test.go):

```go
// fakeSender records what it is asked to send, and fails when err is set.
type fakeSender struct {
	err  error
	sent []string
}

func (f *fakeSender) Send(_ context.Context, to, _ string) error {
	if f.err != nil {
		return f.err
	}
	f.sent = append(f.sent, to)
	return nil
}

func TestWelcomeSendsToEachAddress(t *testing.T) {
	fake := &fakeSender{}
	if err := welcome.Welcome(context.Background(), fake, []string{"ada@example.com"}); err != nil {
		t.Fatalf("Welcome: %v", err)
	}
	if len(fake.sent) != 1 {
		t.Fatalf("sent %d messages, want 1", len(fake.sent)) // stop: fake.sent[0] would panic
	}
	if fake.sent[0] != "ada@example.com" {
		t.Errorf("sent to %q, want ada@example.com", fake.sent[0])
	}
}

func TestWelcomeWrapsTheSendError(t *testing.T) {
	boom := errors.New("smtp down")
	err := welcome.Welcome(context.Background(), &fakeSender{err: boom}, []string{"ada@example.com"})
	if !errors.Is(err, boom) {
		t.Fatalf("err = %v, want it to wrap %v", err, boom)
	}
}
```

The length check uses `t.Fatalf`, so the test stops before `fake.sent[0]` can panic on an empty slice.

If a project already generates mocks, use `go.uber.org/mock`, the maintained fork. `github.com/golang/mock` is archived. Do not add a mocking library to a project that does not have one.

## Golden files

A golden file contains the expected output of a test. The `-update` flag rewrites it from the current output, so a reviewer sees the change in the diff. Check the write's error. Otherwise a failed write leaves the old file in place, and the test compares against stale output.

From [`examples/textutil/textutil_test.go`](../examples/textutil/textutil_test.go):

```go
var update = flag.Bool("update", false, "rewrite golden files in testdata")

func TestRenderMatchesGoldenFile(t *testing.T) {
	got := textutil.Render("Fruit", []string{"apple", "pear"})
	golden := filepath.Join("testdata", "render.golden")

	if *update {
		if err := os.WriteFile(golden, []byte(got), 0o600); err != nil {
			t.Fatalf("update golden file: %v", err)
		}
	}
	want, err := os.ReadFile(golden) // #nosec G304 -- a fixed path in testdata
	if err != nil {
		t.Fatalf("read golden file (run with -update to create it): %v", err)
	}
	if got != string(want) {
		t.Errorf("Render output differs from %s\ngot:\n%s\nwant:\n%s", golden, got, want)
	}
}
```

Run `go test ./textutil -run TestRender -update` to rewrite it. Pass `-update` only to the package that defines the flag: other packages' test binaries reject an unknown flag. Files under `testdata/` are ignored by the go tool's package build.

## Fuzzing

A fuzz test checks a property that is true for every input. Here the property is that reversing twice gives back the input. `go test` runs the seed inputs as ordinary cases. `go test -fuzz=FuzzReverse` generates new inputs until it finds a failure or is stopped, and saves failing inputs under `testdata/fuzz/` so they become regression cases.

From [`examples/textutil/textutil_test.go`](../examples/textutil/textutil_test.go):

```go
func FuzzReverse(f *testing.F) {
	for _, seed := range []string{"", "hello", "héllo, 世界"} {
		f.Add(seed)
	}
	f.Fuzz(func(t *testing.T, s string) {
		if !utf8.ValidString(s) {
			t.Skip("Reverse is defined for valid UTF-8 only")
		}
		rev := textutil.Reverse(s)
		if !utf8.ValidString(rev) {
			t.Fatalf("Reverse(%q) = %q, which is not valid UTF-8", s, rev)
		}
		if again := textutil.Reverse(rev); again != s {
			t.Fatalf("Reverse(Reverse(%q)) = %q", s, again)
		}
	})
}
```

Skip inputs outside the function's contract with `t.Skip`, as here for invalid UTF-8, instead of reporting them as failures.

## The race detector

`go test -race` reports two goroutines that access the same memory, at least one of them writing, without synchronisation. It only finds races in code that runs, so the test must drive the concurrent paths. A test like this one fails under `-race` if `Counter` drops its mutex:

From [`examples/metrics/metrics_test.go`](../examples/metrics/metrics_test.go):

```go
func TestCounterIsSafeForConcurrentUse(t *testing.T) {
	var c metrics.Counter
	var wg sync.WaitGroup
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			c.Inc()
		}()
	}
	wg.Wait()
	if got := c.Value(); got != 50 {
		t.Fatalf("Value() = %d, want 50", got)
	}
}
```

The counter itself:

From [`examples/metrics/metrics.go`](../examples/metrics/metrics.go):

```go
// Counter is a counter that is safe for concurrent use.
type Counter struct {
	mu sync.Mutex
	n  int
}

// Inc adds one to the counter.
func (c *Counter) Inc() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.n++
}

// Value returns the current count.
func (c *Counter) Value() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.n
}
```

## Tests behind a build tag

Slow tests or tests that need outside services can sit behind a build tag.

From Go 1.17, the syntax is `//go:build`. It must come before the `package` clause, with only blank lines and other `//` comments, such as a licence header, above it. Otherwise Go treats it as an ordinary comment and the constraint does nothing. Leave a blank line after it, as `gofmt` does.

A file has at most one `//go:build` line. That line combines conditions with `&&`, `||`, and `!`. The old `// +build` lines are not needed from Go 1.17. `go fix` removes them in modules that declare Go 1.18 or later.

This test runs only with `go test -tags=integration ./...`. It starts a real HTTP server with `httptest`. The server is ready as soon as `NewServer` returns, so the test does not sleep.

From [`examples/health/health_integration_test.go`](../examples/health/health_integration_test.go):

```go
//go:build integration

package health_test

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"example.com/golang-practices/health"
)

// TestCheckAgainstAServer runs only with -tags=integration. The build
// constraint is the first line of the file, followed by a blank line.
func TestCheckAgainstAServer(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(health.Handler))
	t.Cleanup(srv.Close) // ready as soon as NewServer returns: no sleep needed

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := health.Check(ctx, srv.Client(), srv.URL); err != nil {
		t.Fatalf("Check: %v", err)
	}
}
```

`testing.Short()` with `go test -short` is the other way to skip slow tests. It needs no separate build.

## Testable examples

The go tool compiles a function named `ExampleX` in a test file, and shows it in the package documentation beside `X`. `go test` runs it and compares what it prints with the `// Output:` comment. A comment `// Unordered output:` compares the lines in any order, for output such as map iteration.

From [`examples/textutil/example_test.go`](../examples/textutil/example_test.go):

```go
func ExampleReverse() {
	fmt.Println(textutil.Reverse("héllo"))
	// Output: olléh
}

func ExampleRender() {
	fmt.Print(textutil.Render("Fruit", []string{"apple", "pear"}))
	// Output:
	// # Fruit
	//
	// - apple
	// - pear
}
```

## Coverage

The test command in [checks.md](checks.md) writes the coverage profile `coverage.out`. To see which lines run, run that command, then open the profile as annotated source in a browser:

```sh
go tool cover -html=coverage.out
```

Coverage shows which lines no test runs. It does not show whether the tests check the right things. Look at uncovered new code and decide whether a regression there would go unnoticed. A percentage target is not a goal in itself.

## Quick reference

For the test command CI runs, see [checks.md](checks.md).

| Command | What it does |
| --- | --- |
| `go test -run 'TestReverse/ascii' ./textutil` | Run one subtest |
| `go test -count=1 ./...` | Run without the test cache |
| `go test -short ./...` | Skip tests that check `testing.Short()` |
| `go test -tags=integration ./...` | Include files behind `//go:build integration` |
| `go test -fuzz=FuzzReverse ./textutil` | Fuzz one target in one package |
| `go test -bench=. -benchmem ./...` | Run benchmarks; see `performance.md` |
