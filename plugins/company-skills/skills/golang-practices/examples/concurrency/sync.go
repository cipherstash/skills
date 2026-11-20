package concurrency

import (
	"context"
	"fmt"
	"sync"
)

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
