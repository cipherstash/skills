package concurrency_test

import (
	"context"
	"errors"
	"sync"
	"testing"
	"time"

	"example.com/golang-practices/concurrency"
)

func TestCounterIsSafeForConcurrentUse(t *testing.T) {
	var c concurrency.Counter
	var wg sync.WaitGroup
	for range 50 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			c.Increment()
		}()
	}
	wg.Wait()
	if got := c.Value(); got != 50 {
		t.Fatalf("Value = %d, want 50", got)
	}
}

func TestCacheSetAndGet(t *testing.T) {
	c := concurrency.NewCache()
	if _, ok := c.Get("k"); ok {
		t.Fatal("Get on an empty cache reported a value")
	}
	c.Set("k", "v")
	if got, ok := c.Get("k"); !ok || got != "v" {
		t.Fatalf("Get = %q, %v; want %q, true", got, ok, "v")
	}
}

func TestConfigLoadsOnceAndKeepsTheError(t *testing.T) {
	errMissing := errors.New("missing")
	calls := 0
	cfg := concurrency.NewConfig(func() (map[string]string, error) {
		calls++
		return nil, errMissing
	})
	var wg sync.WaitGroup
	for range 10 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			if _, err := cfg.Get(); !errors.Is(err, errMissing) {
				t.Errorf("Get error = %v, want it to wrap %v", err, errMissing)
			}
		}()
	}
	wg.Wait()
	if calls != 1 {
		t.Fatalf("load ran %d times, want 1", calls)
	}
}

func TestSemaphoreAcquireHonoursItsContext(t *testing.T) {
	sem := concurrency.NewSemaphore(1)
	if err := sem.Acquire(context.Background()); err != nil {
		t.Fatalf("first Acquire: %v", err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	if err := sem.Acquire(ctx); !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("Acquire on a full semaphore = %v, want context.DeadlineExceeded", err)
	}
	sem.Release()
	if err := sem.Acquire(context.Background()); err != nil {
		t.Fatalf("Acquire after Release: %v", err)
	}
}

func TestSemaphoreDoReleasesTheSlot(t *testing.T) {
	sem := concurrency.NewSemaphore(1)
	for range 3 {
		if err := sem.Do(context.Background(), func() {}); err != nil {
			t.Fatalf("Do: %v", err)
		}
	}
}
