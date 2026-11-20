package concurrency_test

import (
	"context"
	"errors"
	"sync/atomic"
	"testing"
	"time"

	"example.com/golang-practices/concurrency"
)

func runInBackground(ctx context.Context, s *concurrency.Service) <-chan error {
	errCh := make(chan error, 1)
	go func() { errCh <- s.Run(ctx) }()
	return errCh
}

func waitFor(t *testing.T, errCh <-chan error) error {
	t.Helper()
	select {
	case err := <-errCh:
		return err
	case <-time.After(prompt):
		t.Fatal("Run did not return")
		return nil
	}
}

func TestServiceStopTwiceDoesNotPanic(t *testing.T) {
	s := concurrency.NewService(time.Millisecond, func(context.Context) error { return nil })
	errCh := runInBackground(context.Background(), s)
	s.Stop()
	s.Stop()
	if err := waitFor(t, errCh); err != nil {
		t.Fatalf("Run after Stop = %v, want nil", err)
	}
}

func TestServiceStopsWhenItsContextIsCancelled(t *testing.T) {
	var ticks atomic.Int64
	s := concurrency.NewService(time.Millisecond, func(context.Context) error {
		ticks.Add(1)
		return nil
	})
	ctx, cancel := context.WithCancel(context.Background())
	errCh := runInBackground(ctx, s)
	for ticks.Load() == 0 {
		time.Sleep(time.Millisecond)
	}
	cancel()
	if err := waitFor(t, errCh); !errors.Is(err, context.Canceled) {
		t.Fatalf("Run after cancel = %v, want context.Canceled", err)
	}
}

func TestServiceReturnsTheTickError(t *testing.T) {
	errBoom := errors.New("boom")
	s := concurrency.NewService(time.Millisecond, func(context.Context) error { return errBoom })
	if err := waitFor(t, runInBackground(context.Background(), s)); !errors.Is(err, errBoom) {
		t.Fatalf("Run = %v, want it to wrap %v", err, errBoom)
	}
}
