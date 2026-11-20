package concurrency

import (
	"context"
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
func NewService(interval time.Duration, tick func(context.Context) error) *Service {
	return &Service{interval: interval, tick: tick, stop: make(chan struct{})}
}

// Run calls tick every interval. It returns nil after Stop, ctx's error when
// ctx ends, or the first error from tick.
func (s *Service) Run(ctx context.Context) error {
	ticker := time.NewTicker(s.interval)
	defer ticker.Stop()
	for {
		select {
		case <-s.stop:
			return nil
		case <-ctx.Done():
			return fmt.Errorf("service stopped: %w", ctx.Err())
		case <-ticker.C:
			if err := s.tick(ctx); err != nil {
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
