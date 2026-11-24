package metrics

import "sync"

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
