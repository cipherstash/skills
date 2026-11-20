package concurrency_test

import (
	"context"
	"errors"
	"sync/atomic"
	"testing"
	"time"

	"example.com/golang-practices/concurrency"
)

// prompt is how long a call may take before the test treats it as having
// waited for a timeout or blocked. It is far below the timeouts the tests set.
const prompt = 2 * time.Second

func TestRunJobsReturnsPromptlyOnSuccess(t *testing.T) {
	// The upstream example waited for its whole timeout on success and then
	// reported a timeout. Give the call a long deadline and require it to
	// finish well inside it, with no error.
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	var processed atomic.Int64
	jobs := []concurrency.Job{{ID: 1}, {ID: 2}, {ID: 3}}
	start := time.Now()
	err := concurrency.RunJobs(ctx, jobs, func(ctx context.Context, j concurrency.Job) error {
		processed.Add(1)
		return nil
	})
	if err != nil {
		t.Fatalf("RunJobs: %v", err)
	}
	if elapsed := time.Since(start); elapsed > prompt {
		t.Fatalf("RunJobs took %v on success; it should not wait for the deadline", elapsed)
	}
	if got := processed.Load(); got != int64(len(jobs)) {
		t.Fatalf("processed %d jobs, want %d", got, len(jobs))
	}
}

func TestRunJobsReturnsTheFirstFailure(t *testing.T) {
	errBoom := errors.New("boom")
	jobs := []concurrency.Job{{ID: 1}, {ID: 2}, {ID: 3}}
	err := concurrency.RunJobs(context.Background(), jobs, func(ctx context.Context, j concurrency.Job) error {
		if j.ID == 2 {
			return errBoom
		}
		return nil
	})
	if !errors.Is(err, errBoom) {
		t.Fatalf("RunJobs error = %v, want it to wrap %v", err, errBoom)
	}
	if want := "process job 2: boom"; err.Error() != want {
		t.Fatalf("RunJobs error = %q, want %q", err, want)
	}
}

func TestRunJobsStopsWhenTheContextEnds(t *testing.T) {
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()

	jobs := []concurrency.Job{{ID: 1}, {ID: 2}}
	start := time.Now()
	err := concurrency.RunJobs(ctx, jobs, func(ctx context.Context, j concurrency.Job) error {
		<-ctx.Done() // a job that only ends when it is cancelled
		return ctx.Err()
	})
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("RunJobs error = %v, want context.DeadlineExceeded", err)
	}
	if elapsed := time.Since(start); elapsed > prompt {
		t.Fatalf("RunJobs took %v after its deadline", elapsed)
	}
}

func TestRunJobsRunsNothingWhenTheContextHasAlreadyEnded(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	// select picks at random among ready cases, so try many times.
	for range 200 {
		var processed atomic.Int64
		err := concurrency.RunJobs(ctx, []concurrency.Job{{ID: 1}}, func(context.Context, concurrency.Job) error {
			processed.Add(1)
			return nil
		})
		if !errors.Is(err, context.Canceled) {
			t.Fatalf("RunJobs error = %v, want context.Canceled", err)
		}
		if got := processed.Load(); got != 0 {
			t.Fatalf("processed %d jobs after the context ended, want 0", got)
		}
	}
}
