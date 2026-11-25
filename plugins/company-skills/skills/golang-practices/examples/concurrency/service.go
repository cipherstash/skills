package concurrency

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"time"
)

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
