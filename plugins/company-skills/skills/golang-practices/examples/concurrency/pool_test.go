package concurrency_test

import (
	"context"
	"errors"
	"sync/atomic"
	"testing"
	"time"

	"example.com/golang-practices/concurrency"
)

func TestPoolRunsEveryAcceptedTaskBeforeShutdownReturns(t *testing.T) {
	pool := concurrency.NewPool(3)
	var ran atomic.Int64
	for range 20 {
		if err := pool.Submit(context.Background(), func(context.Context) { ran.Add(1) }); err != nil {
			t.Fatalf("Submit: %v", err)
		}
	}
	if err := pool.Shutdown(context.Background()); err != nil {
		t.Fatalf("Shutdown: %v", err)
	}
	if got := ran.Load(); got != 20 {
		t.Fatalf("ran %d tasks, want 20", got)
	}
}

func TestPoolShutdownTwiceDoesNotPanic(t *testing.T) {
	pool := concurrency.NewPool(2)
	if err := pool.Shutdown(context.Background()); err != nil {
		t.Fatalf("first Shutdown: %v", err)
	}
	if err := pool.Shutdown(context.Background()); err != nil {
		t.Fatalf("second Shutdown: %v", err)
	}
}

func TestPoolSubmitAfterShutdownReturnsErrPoolClosed(t *testing.T) {
	pool := concurrency.NewPool(1)
	if err := pool.Shutdown(context.Background()); err != nil {
		t.Fatalf("Shutdown: %v", err)
	}
	err := pool.Submit(context.Background(), func(context.Context) {})
	if !errors.Is(err, concurrency.ErrPoolClosed) {
		t.Fatalf("Submit after Shutdown = %v, want ErrPoolClosed", err)
	}
}

func TestPoolSubmitHonoursItsContext(t *testing.T) {
	pool := concurrency.NewPool(1)
	release := make(chan struct{})
	started := make(chan struct{})
	if err := pool.Submit(context.Background(), func(context.Context) {
		close(started)
		<-release
	}); err != nil {
		t.Fatalf("Submit: %v", err)
	}
	<-started // the only worker is now busy

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	err := pool.Submit(ctx, func(context.Context) {})
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("Submit to a busy pool = %v, want context.DeadlineExceeded", err)
	}

	close(release)
	if err := pool.Shutdown(context.Background()); err != nil {
		t.Fatalf("Shutdown: %v", err)
	}
}

func TestPoolShutdownCancelsTasksWhenItsContextEnds(t *testing.T) {
	pool := concurrency.NewPool(1)
	stopped := make(chan struct{})
	if err := pool.Submit(context.Background(), func(ctx context.Context) {
		<-ctx.Done() // a task that runs until it is cancelled
		close(stopped)
	}); err != nil {
		t.Fatalf("Submit: %v", err)
	}

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	if err := pool.Shutdown(ctx); !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("Shutdown = %v, want context.DeadlineExceeded", err)
	}
	select {
	case <-stopped:
	case <-time.After(prompt):
		t.Fatal("the running task was not cancelled after Shutdown gave up waiting")
	}
}
