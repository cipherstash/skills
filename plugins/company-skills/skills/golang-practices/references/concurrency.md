# Concurrency

Goroutines, channels, `select`, the `sync` package, and how work started in the background is stopped.

The examples target Go 1.22, the `go` line in [`examples/go.mod`](../examples/go.mod). Each one is quoted from the examples module, where tests check the behaviour the text describes, and `go vet` and `go test -race` run over it in CI. Where advice depends on the Go version, the text says so.

## Contents

- [Rules](#rules)
- [Run work in the background and wait for it](#run-work-in-the-background-and-wait-for-it)
- [Worker pool](#worker-pool)
- [Generator, fan-out, and fan-in](#generator-fan-out-and-fan-in)
- [Pipeline](#pipeline)
- [Blocking calls take a context](#blocking-calls-take-a-context)
- [Stopping a long-running loop](#stopping-a-long-running-loop)
- [Mutexes and one-time initialisation](#mutexes-and-one-time-initialisation)
- [Limiting concurrency and rate](#limiting-concurrency-and-rate)
- [Loop variables and Go versions](#loop-variables-and-go-versions)
- [Quick reference](#quick-reference)

## Rules

- Before starting a goroutine, know how it stops and who waits for it. A goroutine ends when its work is done, its context ends, or its owner stops it. Something waits for it to end.
- Every channel send and receive that can block also selects on `ctx.Done()` (or another stop signal). A `for v := range in` loop is safe only when the sender is certain to close `in`.
- A function that blocks on I/O, a long-held lock, or another goroutine takes a `context.Context` first. It returns when the context ends.
- Return when the work is done. Waiting on `ctx.Done()` as the only way out turns every success into a timeout.
- The sender closes a channel, once. Receivers never close it.
- A stop or shutdown method is safe to call more than once and from several goroutines.
- Report a goroutine's error to whoever waits for it. A goroutine that drops its error hides the failure.
- Run tests with `-race`. [checks.md](checks.md) gives the command CI runs. A data race is a bug even when the test passes.

## Run work in the background and wait for it

`RunJobs` hands jobs to a worker goroutine and waits for one of three outcomes: every job processed, a job failed, or the context ended. The worker sends exactly one result, `nil` on success. So the caller returns as soon as the work is done, not when a timeout expires.

From [`examples/concurrency/jobs.go`](../examples/concurrency/jobs.go):

```go
// Job is one unit of work for RunJobs.
type Job struct {
	ID int
}

// RunJobs processes jobs in order on one background worker. It returns nil
// as soon as every job has been processed, the first processing error, or
// the context's error if ctx ends first. The worker has exited by the time
// RunJobs returns.
func RunJobs(ctx context.Context, jobs []Job, process func(context.Context, Job) error) error {
	jobCh := make(chan Job)
	errCh := make(chan error, 1) // the worker sends exactly one value, then exits
	go func() { errCh <- worker(ctx, jobCh, process) }()

	for _, j := range jobs {
		select {
		case jobCh <- j:
		case err := <-errCh:
			// The worker stopped early because a job failed or ctx ended.
			return err
		}
	}
	close(jobCh)
	return <-errCh // nil once the worker has drained jobCh
}

// worker processes jobs until jobs is closed, a job fails, or ctx ends.
func worker(ctx context.Context, jobs <-chan Job, process func(context.Context, Job) error) error {
	for {
		// select picks at random among ready cases, so check ctx first: a
		// context that has already ended must not start another job.
		if err := ctx.Err(); err != nil {
			return fmt.Errorf("worker stopped: %w", err)
		}
		select {
		case <-ctx.Done():
			return fmt.Errorf("worker stopped: %w", ctx.Err())
		case job, ok := <-jobs:
			if !ok {
				return nil // jobs closed: all work is done
			}
			if err := process(ctx, job); err != nil {
				return fmt.Errorf("process job %d: %w", job.ID, err)
			}
		}
	}
}
```

The caller decides the deadline, so `RunJobs` has no timeout of its own. On success it returns at once, long before the 30 seconds pass:

From [`examples/concurrency/example_test.go`](../examples/concurrency/example_test.go):

```go
func ExampleRunJobs() {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	jobs := []concurrency.Job{{ID: 1}, {ID: 2}}
	err := concurrency.RunJobs(ctx, jobs, func(ctx context.Context, j concurrency.Job) error {
		fmt.Println("processed job", j.ID)
		return nil
	})
	fmt.Println("error:", err)
	// Output:
	// processed job 1
	// processed job 2
	// error: <nil>
}
```

Points to keep:

- `errCh` has a buffer of one, so the worker's final send never blocks, even when `RunJobs` has already returned.
- The send loop also selects on `errCh`. If the worker stops early, the loop stops sending instead of blocking on a channel nobody reads.
- When several goroutines share the work and the first error should cancel the rest, use `golang.org/x/sync/errgroup` with `errgroup.WithContext`. It does the waiting and error collection this example does by hand.

## Worker pool

A pool runs submitted tasks on a fixed number of goroutines. `Submit` takes a context because it blocks until a worker is free. `Shutdown` takes a context because waiting for running tasks can take a long time. Each task receives a context that is cancelled if `Shutdown` stops waiting, so tasks have a way to stop too.

From [`examples/concurrency/pool.go`](../examples/concurrency/pool.go):

```go
// ErrPoolClosed is returned by Submit after Shutdown has been called.
var ErrPoolClosed = errors.New("pool closed")

// Pool runs submitted tasks on a fixed number of goroutines.
type Pool struct {
	tasks    chan func(context.Context)
	quit     chan struct{} // closed by Shutdown: no new tasks
	done     chan struct{} // closed when every worker has exited
	stopOnce sync.Once
	cancel   context.CancelFunc // cancels the context running tasks receive
}

// NewPool starts a pool of n workers. Call Shutdown to stop them. It panics
// if n is less than 1: a pool with no workers would block every Submit.
func NewPool(n int) *Pool {
	if n < 1 {
		panic("concurrency: NewPool needs at least 1 worker")
	}
	ctx, cancel := context.WithCancel(context.Background())
	p := &Pool{
		tasks:  make(chan func(context.Context)),
		quit:   make(chan struct{}),
		done:   make(chan struct{}),
		cancel: cancel,
	}
	var wg sync.WaitGroup
	for range n {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for {
				select {
				case <-p.quit:
					return
				case task := <-p.tasks:
					task(ctx)
				}
			}
		}()
	}
	go func() {
		wg.Wait()
		close(p.done)
	}()
	return p
}

// Submit hands task to a free worker. It blocks until a worker accepts the
// task, ctx ends, or the pool is shut down. A task accepted while Shutdown
// is starting still runs before Shutdown returns.
func (p *Pool) Submit(ctx context.Context, task func(context.Context)) error {
	select {
	case p.tasks <- task:
		return nil
	case <-p.quit:
		return ErrPoolClosed
	case <-ctx.Done():
		return fmt.Errorf("submit task: %w", ctx.Err())
	}
}

// Shutdown stops the pool from accepting tasks and waits for running tasks
// to finish. If ctx ends first, it cancels the context the running tasks
// received and returns ctx's error. It is safe to call more than once and
// from several goroutines.
func (p *Pool) Shutdown(ctx context.Context) error {
	p.stopOnce.Do(func() { close(p.quit) })
	select {
	case <-p.done:
		p.cancel()
		return nil
	case <-ctx.Done():
		p.cancel()
		return fmt.Errorf("shut down pool: %w", ctx.Err())
	}
}
```

Points to keep:

- `Shutdown` closes `quit` inside a `sync.Once`. Closing a closed channel panics, so a bare `close` makes a second call crash.
- The pool never closes `tasks`. A send on a closed channel panics, and `Submit` could race with `Shutdown`. `Submit` returns `ErrPoolClosed` instead.
- `tasks` is unbuffered, so `Shutdown` has no queue to drain or drop. Every task `Submit` accepted is already with a worker.

## Generator, fan-out, and fan-in

A generator returns a receive-only channel and closes it when it has no more values. Each stage selects on `ctx.Done()` around both its receive and its send. So it stops when the context ends, even if nobody closes its input or reads its output.

From [`examples/concurrency/channels.go`](../examples/concurrency/channels.go):

```go
// Generate sends 0 to n-1 on the returned channel, then closes it. It stops
// early and closes the channel when ctx ends.
func Generate(ctx context.Context, n int) <-chan int {
	out := make(chan int)
	go func() {
		defer close(out)
		for i := range n {
			select {
			case out <- i:
			case <-ctx.Done():
				return
			}
		}
	}()
	return out
}

// Double sends twice each value from in. It closes its output when in is
// closed or ctx ends, so it stops even if in is never closed.
func Double(ctx context.Context, in <-chan int) <-chan int {
	out := make(chan int)
	go func() {
		defer close(out)
		for {
			select {
			case v, ok := <-in:
				if !ok {
					return
				}
				select {
				case out <- v * 2:
				case <-ctx.Done():
					return
				}
			case <-ctx.Done():
				return
			}
		}
	}()
	return out
}

// FanOut starts n Double stages that share in.
func FanOut(ctx context.Context, in <-chan int, n int) []<-chan int {
	outs := make([]<-chan int, n)
	for i := range outs {
		outs[i] = Double(ctx, in)
	}
	return outs
}

// Merge sends every value from every input on one channel. It closes its
// output when all inputs are closed or ctx ends.
func Merge(ctx context.Context, ins ...<-chan int) <-chan int {
	out := make(chan int)
	var wg sync.WaitGroup
	for _, in := range ins {
		wg.Add(1)
		go func() { // Go 1.22+: each iteration has its own in
			defer wg.Done()
			for {
				select {
				case v, ok := <-in:
					if !ok {
						return
					}
					select {
					case out <- v:
					case <-ctx.Done():
						return
					}
				case <-ctx.Done():
					return
				}
			}
		}()
	}
	go func() {
		wg.Wait()
		close(out)
	}()
	return out
}
```

`FanOut` starts several `Double` stages on one input, and `Merge` combines their outputs. `Merge` uses a `sync.WaitGroup` to close its output only after every input goroutine has finished.

Whoever reads the merged channel either reads it to the end or cancels `ctx` when it stops early. Otherwise the stages block on their sends.

## Pipeline

A pipeline chains stages. Here a squaring stage feeds a filter that keeps even numbers, and both share one stage function.

From [`examples/concurrency/channels.go`](../examples/concurrency/channels.go):

```go
// Pipeline squares each value from in and passes on the even results. Both
// stages stop when in is closed or ctx ends.
func Pipeline(ctx context.Context, in <-chan int) <-chan int {
	squares := stage(ctx, in, func(n int) (int, bool) { return n * n, true })
	return stage(ctx, squares, func(n int) (int, bool) { return n, n%2 == 0 })
}

// stage runs one pipeline step in its own goroutine. f returns the value to
// send and whether to send it.
func stage(ctx context.Context, in <-chan int, f func(int) (int, bool)) <-chan int {
	out := make(chan int)
	go func() {
		defer close(out)
		for {
			select {
			case n, ok := <-in:
				if !ok {
					return
				}
				v, keep := f(n)
				if !keep {
					continue
				}
				select {
				case out <- v:
				case <-ctx.Done():
					return
				}
			case <-ctx.Done():
				return
			}
		}
	}()
	return out
}
```

Use a pipeline for a stream of values where each stage can run at its own pace. For a fixed list of independent jobs, the worker in [Run work in the background and wait for it](#run-work-in-the-background-and-wait-for-it) or `errgroup` is simpler.

## Blocking calls take a context

Pass the context to the call that blocks. `http.NewRequestWithContext` ties the request to `ctx`, so `client.Do` returns when the deadline passes. There is no need for a goroutine, a result channel, or `time.After`. `client.Do` returns a `*url.Error`, which already names the method and the URL, so `Fetch` returns it as it is.

From [`examples/concurrency/fetch.go`](../examples/concurrency/fetch.go):

```go
// StatusError reports a response whose status code was not 200 OK.
type StatusError struct {
	URL  string
	Code int
}

func (e *StatusError) Error() string {
	return fmt.Sprintf("get %s: unexpected status %d %s", e.URL, e.Code, http.StatusText(e.Code))
}

// Fetch returns the body of url. The request stops when ctx ends, so the
// caller sets the timeout:
//
//	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
//	defer cancel()
//	body, err := Fetch(ctx, http.DefaultClient, url)
func Fetch(ctx context.Context, client *http.Client, url string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("build request: %w", err) // the *url.Error names the URL
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err // a *url.Error, which names the method and the URL
	}
	defer resp.Body.Close() // read-only: a close error cannot lose data
	if resp.StatusCode != http.StatusOK {
		// Read a little of the body so the connection can be reused.
		_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, 4<<10))
		return nil, &StatusError{URL: req.URL.Redacted(), Code: resp.StatusCode}
	}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read body of %s: %w", req.URL.Redacted(), err)
	}
	return body, nil
}
```

Fetch's own errors name the URL with `req.URL.Redacted()`, which hides a password in it, as `client.Do`'s `*url.Error` already does. On a status other than 200, it reads up to 4 KiB of the body before it closes it, so the connection goes back to the pool instead of being closed.

Do not wrap a blocking call that ignores `ctx` in a goroutine and race it against a timer. The caller gets an answer on time, but the call keeps running in the background, still holding its connection, and its result is thrown away. Find or write the variant that takes a context: `net.Dialer.DialContext`, `sql.DB.QueryContext`, `exec.CommandContext`, and so on.

`context.WithTimeout` and `context.WithDeadline` return a cancel function. Call it, usually with `defer cancel()`, so the timer is released as soon as the work finishes. `go vet` reports a cancel function that is never called.

## Stopping a long-running loop

`Run` loops until its context ends or `Stop` is called. `Stop` closes the channel inside a `sync.Once`, so calling it twice, or from two goroutines, is safe. `Run` passes `tick` a context derived from its own and cancels it when `Stop` is called, so a tick that is blocked when `Stop` is called also returns. A tick error after `Stop` counts as the stop only when it is `context.Canceled`; any other tick error, such as a failed write, is still returned. `Run` waits for the goroutine that watches `Stop` to exit before it returns.

From [`examples/concurrency/service.go`](../examples/concurrency/service.go):

```go
// Service calls tick on a fixed interval until it is stopped.
type Service struct {
	interval time.Duration
	tick     func(context.Context) error
	stop     chan struct{}
	stopOnce sync.Once
}

// NewService returns a Service that calls tick every interval once Run starts.
// It panics if interval is not positive, as time.NewTicker would once Run
// starts.
func NewService(interval time.Duration, tick func(context.Context) error) *Service {
	if interval <= 0 {
		panic("concurrency: NewService needs a positive interval")
	}
	return &Service{interval: interval, tick: tick, stop: make(chan struct{})}
}

// Run calls tick every interval. It returns nil after Stop, ctx's error when
// ctx ends, or the first error from tick. Stop also cancels the context that a
// running tick receives, so a tick that blocks until its context ends does not
// keep Run from returning. A tick error caused by that cancellation counts as
// the Stop, and Run returns nil; any other tick error is returned.
func (s *Service) Run(ctx context.Context) error {
	ctx, cancel := context.WithCancel(ctx)
	done := make(chan struct{})
	defer func() {
		cancel()
		<-done // the goroutine below has exited
	}()
	go func() {
		defer close(done)
		select {
		case <-s.stop:
			cancel()
		case <-ctx.Done():
		}
	}()
	ticker := time.NewTicker(s.interval)
	defer ticker.Stop()
	for {
		select {
		case <-s.stop:
			return nil
		case <-ctx.Done():
			if s.stopped() {
				return nil
			}
			return fmt.Errorf("service stopped: %w", ctx.Err())
		case <-ticker.C:
			if err := s.tick(ctx); err != nil {
				if s.stopped() && errors.Is(err, context.Canceled) {
					return nil
				}
				return fmt.Errorf("tick: %w", err)
			}
		}
	}
}

// Stop makes Run return. It is safe to call more than once and from several
// goroutines.
func (s *Service) Stop() {
	s.stopOnce.Do(func() { close(s.stop) })
}

func (s *Service) stopped() bool {
	select {
	case <-s.stop:
		return true
	default:
		return false
	}
}
```

Prefer the context alone when the code that starts `Run` also stops it. Cancel the context; calling the cancel function again does nothing. Add a `Stop` method only when something without access to that context must stop the loop.

`Run` returns the tick error rather than printing it, and the caller decides whether to log, retry, or exit.

## Mutexes and one-time initialisation

Protect shared state with a mutex held for the shortest time that keeps it consistent. Keep the mutex next to the fields it guards, and never copy a struct that contains one: `go vet` reports copies.

From [`examples/concurrency/sync.go`](../examples/concurrency/sync.go):

```go
// Counter is a count that is safe for concurrent use. Its zero value is
// ready to use.
type Counter struct {
	mu    sync.Mutex
	count int
}

// Increment adds one to the count.
func (c *Counter) Increment() {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.count++
}

// Value returns the count.
func (c *Counter) Value() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.count
}

// Cache is a string map for read-heavy concurrent use.
type Cache struct {
	mu    sync.RWMutex
	items map[string]string
}

// NewCache returns an empty Cache. The zero value is not usable: Set would
// write to a nil map and panic.
func NewCache() *Cache {
	return &Cache{items: make(map[string]string)}
}

// Get returns the value for key and whether it was present.
func (c *Cache) Get(key string) (string, bool) {
	c.mu.RLock()
	defer c.mu.RUnlock()
	v, ok := c.items[key]
	return v, ok
}

// Set stores value under key.
func (c *Cache) Set(key, value string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.items[key] = value
}
```

A struct with a map needs a constructor, or every method must create the map on first use, because writing to a nil map panics. Use `sync.RWMutex` only when reads far outnumber writes and are slow enough to matter; otherwise `sync.Mutex` is simpler and often faster.

For a value computed once on first use, use `sync.OnceValue` or `sync.OnceValues` (Go 1.21 and later). They keep the error as well as the value, so the failure is not lost after the first call.

From [`examples/concurrency/sync.go`](../examples/concurrency/sync.go):

```go
// Config loads its settings once, on first use, and keeps the result,
// including a load error, for every later call.
type Config struct {
	load func() (map[string]string, error)
}

// NewConfig returns a Config that calls load at most once.
func NewConfig(load func() (map[string]string, error)) *Config {
	return &Config{load: sync.OnceValues(load)}
}

// Get returns the settings, loading them on the first call.
func (c *Config) Get() (map[string]string, error) {
	settings, err := c.load()
	if err != nil {
		return nil, fmt.Errorf("load config: %w", err)
	}
	return settings, nil
}
```

## Limiting concurrency and rate

A buffered channel makes a counting semaphore. `Acquire` takes a context, because waiting for a free slot is a blocking call.

From [`examples/concurrency/sync.go`](../examples/concurrency/sync.go):

```go
// Semaphore limits how many goroutines run a section at once.
type Semaphore struct {
	slots chan struct{}
}

// NewSemaphore returns a Semaphore with n slots. It panics if n is less
// than 1: a semaphore with no slots would block every Acquire.
func NewSemaphore(n int) *Semaphore {
	if n < 1 {
		panic("concurrency: NewSemaphore needs at least 1 slot")
	}
	return &Semaphore{slots: make(chan struct{}, n)}
}

// Acquire takes a slot, waiting until one is free or ctx ends.
func (s *Semaphore) Acquire(ctx context.Context) error {
	select {
	case s.slots <- struct{}{}:
		return nil
	case <-ctx.Done():
		return fmt.Errorf("acquire semaphore: %w", ctx.Err())
	}
}

// Release frees a slot taken by Acquire.
func (s *Semaphore) Release() {
	<-s.slots
}

// Do runs fn while holding a slot.
func (s *Semaphore) Do(ctx context.Context, fn func()) error {
	if err := s.Acquire(ctx); err != nil {
		return err
	}
	defer s.Release()
	fn()
	return nil
}
```

For weighted slots, use `golang.org/x/sync/semaphore`. To cap the goroutines an `errgroup.Group` runs, call its `SetLimit` method.

To limit a rate rather than a count, use `golang.org/x/time/rate`. Its `Limiter.Wait(ctx)` blocks until a token is free or the context ends; wrap and return its error. The examples module does not import it, so no example is quoted here.

## Loop variables and Go versions

From Go 1.22, each iteration of a `for` loop has its own loop variable. A goroutine or closure started in the loop sees that iteration's value. `Merge` relies on this. The version that matters is the `go` line in the module's `go.mod`, not the installed toolchain.

For a module whose `go` line is below 1.22, every iteration shares one variable. Pass it to the goroutine as an argument, or copy it (`in := in`) before the goroutine starts. Read the `go` line before adding or removing such a copy.

## Quick reference

| Pattern | Use it for | How it stops |
| --- | --- | --- |
| Background worker (`RunJobs`) | Process a list, wait for the result | Work done, first error, or context ended |
| `errgroup.WithContext` | Several goroutines, first error cancels the rest | Same, with the waiting done for you |
| Worker pool | Bounded concurrency for submitted tasks | `Shutdown`, safe to repeat |
| Generator, fan-out, and fan-in | Spread a stream over goroutines and combine it | Input closed or context ended |
| Pipeline | Stream processing in stages | Input closed or context ended |
| Semaphore | Cap concurrent use of a resource | `Acquire` honours its context |
| `rate.Limiter` | Cap a request rate | `Wait` honours its context |
| `sync.Once`, `sync.OnceValues` | Initialise once, close once | Not applicable |
