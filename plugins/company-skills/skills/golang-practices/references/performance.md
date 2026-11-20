# Performance

Allocation in hot loops, the capacity of slices and maps, building strings, benchmarks, and profiling.

The examples target Go 1.22, the `go` line in [`examples/go.mod`](../examples/go.mod). `b.Loop` needs Go 1.24, as the text says. Each example is quoted from the examples module, where its tests pass and its benchmarks run once in CI.

## Contents

- [Rules](#rules)
- [Size slices and maps up front](#size-slices-and-maps-up-front)
- [Build strings with strings.Builder](#build-strings-with-stringsbuilder)
- [Avoid allocating in hot loops](#avoid-allocating-in-hot-loops)
- [Benchmarks](#benchmarks)
- [Profiling](#profiling)
- [Quick reference](#quick-reference)

## Rules

- Write clear code first. Optimise a path only when a benchmark or profile shows it matters, and keep the benchmark that shows the gain.
- When the final length is known, make a slice with that capacity, `make([]T, 0, n)`, and give a map a size hint, `make(map[K]V, n)`.
- Build strings with `strings.Builder`, `strings.Join`, or `fmt.Fprintf` into a builder, not `+=` in a loop.
- In a loop that runs for every request or record, avoid work that allocates on each pass. Reuse buffers and use the `strconv.Append...` functions. Move constant work, such as compiling a regular expression, out of the loop.
- Measure with `go test -bench=. -benchmem`, and compare runs with `benchstat`, not single numbers.
- Find where the time goes with a CPU profile before changing code. Look for allocations with a memory profile.
- An obvious inefficiency on a hot path is worth fixing in review. A micro-optimisation with no measurement is not.

## Size slices and maps up front

As a slice fills, `append` grows it again and again. Each time, it allocates a larger array and copies the elements. When the final length is known, allocate once:

From [`examples/performance/perf.go`](../examples/performance/perf.go):

```go
// IDs returns the IDs of users. The length is known, so the slice is made
// with that capacity once instead of growing and copying as append fills it.
func IDs(users []User) []int64 {
	ids := make([]int64, 0, len(users))
	for _, u := range users {
		ids = append(ids, u.ID)
	}
	return ids
}

// ByID indexes users by ID. The size hint lets the map allocate its buckets
// once.
func ByID(users []User) map[int64]User {
	m := make(map[int64]User, len(users))
	for _, u := range users {
		m[u.ID] = u
	}
	return m
}
```

When the length is only an upper bound, a capacity of that bound is still usually right. When it is unknown, let `append` grow the slice.

`make([]T, n)` makes a slice of length `n` full of zero values, so `append` adds after them. Use `make([]T, 0, n)` with `append`, or `make([]T, n)` with index assignment.

## Build strings with strings.Builder

A Go string cannot change, so `s += x` copies all of `s` into a new string each time. In a loop, that work grows with the square of the length.

From [`examples/performance/perf.go`](../examples/performance/perf.go):

```go
// JoinNamesConcat joins names with +=. Each += copies the whole string built
// so far, so the work grows with the square of the input. Shown for the
// benchmark; use JoinNames.
func JoinNamesConcat(users []User) string {
	s := ""
	for i, u := range users {
		if i > 0 {
			s += ","
		}
		s += u.Name
	}
	return s
}

// JoinNames joins names with a strings.Builder, which appends to one growing
// buffer. strings.Join does the same for a []string.
func JoinNames(users []User) string {
	var b strings.Builder
	for i, u := range users {
		if i > 0 {
			b.WriteByte(',')
		}
		b.WriteString(u.Name)
	}
	return b.String()
}
```

For 1,000 names, the benchmark below shows the builder about 180 times faster. It makes 15 allocations instead of about 2,000. Those numbers are from Go 1.24.7 on linux/amd64. Yours will differ.

Call `b.Grow(n)` first if you know the final size. For a `[]string` already in hand, `strings.Join` does the same.

`fmt.Sprintf` is convenient but slower than `strconv` for a single number. That matters only on a hot path.

## Avoid allocating in hot loops

A function that returns a new `[]byte` or `string` for every record allocates on every pass. The `append` style takes a buffer and returns it extended, so a caller can reuse one buffer for many records:

From [`examples/performance/perf.go`](../examples/performance/perf.go):

```go
// AppendCSV appends u as a CSV line to dst and returns the extended slice.
// A caller that writes many records reuses one buffer, so the hot loop does
// not allocate. strconv.AppendInt formats without making a string first.
// Names are written as they are: this example assumes they hold no commas.
func AppendCSV(dst []byte, u User) []byte {
	dst = strconv.AppendInt(dst, u.ID, 10)
	dst = append(dst, ',')
	dst = append(dst, u.Name...)
	return append(dst, '\n')
}
```

Other common causes of allocation in loops:

- Converting between `string` and `[]byte`. Each conversion usually copies.
- Passing a non-pointer value to a parameter of type `any` or another interface. The value may move to the heap.
- Compiling a `regexp`, a `template`, or a JSON schema on each call. Compile once, at package level or in a constructor.
- Closures that a goroutine or a later call keeps. The variables they capture then live on the heap.

`go build -gcflags=-m ./pkg` prints the compiler's escape analysis: which values move to the heap and why. `sync.Pool` can reuse large, short-lived buffers between goroutines, but it adds complexity. Use it only when a profile shows that allocating those buffers is the cost.

## Benchmarks

A benchmark runs the code `b.N` times and reports the time per run. `b.ReportAllocs()` adds bytes and allocations per run. Do setup before the loop, and call `b.ResetTimer()` if setup is slow. Store results in a package-level variable, so the compiler cannot remove the work.

From [`examples/performance/perf_test.go`](../examples/performance/perf_test.go):

```go
// sink keeps results alive so the compiler cannot remove the work being
// measured.
var sink string

func BenchmarkJoinNames(b *testing.B) {
	us := users(1000) // setup, before the timer starts
	b.Run("concat", func(b *testing.B) {
		b.ReportAllocs()
		for i := 0; i < b.N; i++ {
			sink = performance.JoinNamesConcat(us)
		}
	})
	b.Run("builder", func(b *testing.B) {
		b.ReportAllocs()
		for i := 0; i < b.N; i++ {
			sink = performance.JoinNames(us)
		}
	})
}

func BenchmarkAppendCSV(b *testing.B) {
	us := users(1000)
	buf := make([]byte, 0, 64*1024)
	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		buf = buf[:0] // reuse the buffer: no allocation once it is big enough
		for _, u := range us {
			buf = performance.AppendCSV(buf, u)
		}
	}
}
```

From Go 1.24, `for b.Loop() { ... }` replaces `for i := 0; i < b.N; i++`. It runs setup only once, keeps results alive, and excludes setup time without `b.ResetTimer`. Use it when the module's `go` line is 1.24 or later.

Compare before and after with several runs:

```sh
go test -run='^$' -bench=JoinNames -benchmem -count=10 ./performance > old.txt
# make the change
go test -run='^$' -bench=JoinNames -benchmem -count=10 ./performance > new.txt
go run golang.org/x/perf/cmd/benchstat@latest old.txt new.txt
```

`benchstat` reports the change and whether it is larger than the noise. Run benchmarks on a quiet machine; numbers from a busy laptop or a shared CI runner vary widely.

## Profiling

Profile a benchmark or a test:

```sh
go test -run='^$' -bench=AppendCSV -cpuprofile=cpu.out -memprofile=mem.out ./performance
go tool pprof -top cpu.out                    # functions using the most CPU
go tool pprof -sample_index=alloc_space -top mem.out   # where memory is allocated
go tool pprof -http=localhost:8080 cpu.out    # flame graph and source view in a browser
```

Profile a running service with `net/http/pprof`. Serve its handlers on a separate listener bound to localhost, such as `localhost:6060`, never on the public port:

From [`examples/performance/debug.go`](../examples/performance/debug.go):

```go
// DebugHandler serves the runtime profiles under /debug/pprof/. Serve it on
// its own listener bound to localhost, never on the public port: profiles
// reveal internals and can be expensive to produce. Importing net/http/pprof
// also registers these handlers on http.DefaultServeMux, so a service must
// not serve DefaultServeMux publicly either.
func DebugHandler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/debug/pprof/", pprof.Index)
	mux.HandleFunc("/debug/pprof/cmdline", pprof.Cmdline)
	mux.HandleFunc("/debug/pprof/profile", pprof.Profile)
	mux.HandleFunc("/debug/pprof/symbol", pprof.Symbol)
	mux.HandleFunc("/debug/pprof/trace", pprof.Trace)
	return mux
}
```

Then fetch a 30-second CPU profile with `go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30`. Use `/debug/pprof/heap` for memory. Use `/debug/pprof/goroutine?debug=2` to see every goroutine's stack and find goroutine leaks.

From Go 1.21, profile-guided optimisation uses a CPU profile from production: put it at `default.pgo` in the main package's directory, and `go build` uses it.

## Quick reference

| Problem | Fix |
| --- | --- |
| `append` in a loop with a known length | `make([]T, 0, n)` |
| Map filled from a known number of items | `make(map[K]V, n)` |
| `s += x` in a loop | `strings.Builder` or `strings.Join` |
| A new buffer for every record | `Append...` functions and a reused buffer |
| `regexp.MustCompile` inside a function called often | Compile once at package level |
| Guessing what is slow | `-cpuprofile` and `go tool pprof` |
| Comparing two single benchmark runs | `-count=10` and `benchstat` |
