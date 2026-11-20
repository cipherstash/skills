package textutil

import (
	"context"
	"fmt"
	"net/http"
	"strings"
	"sync"
)

// Reverse returns s with its runes in reverse order. It works on runes, not
// bytes, so multi-byte UTF-8 characters stay intact.
func Reverse(s string) string {
	r := []rune(s)
	for i, j := 0, len(r)-1; i < j; i, j = i+1, j-1 {
		r[i], r[j] = r[j], r[i]
	}
	return string(r)
}

// Render formats a titled list, one item per line.
func Render(title string, items []string) string {
	var b strings.Builder
	fmt.Fprintf(&b, "# %s\n\n", title)
	for _, item := range items {
		fmt.Fprintf(&b, "- %s\n", item)
	}
	return b.String()
}

// Sender sends a message to an address.
type Sender interface {
	Send(ctx context.Context, to, body string) error
}

// Welcome sends a welcome message to each address, stopping at the first
// failure.
func Welcome(ctx context.Context, s Sender, addrs []string) error {
	for _, to := range addrs {
		if err := s.Send(ctx, to, "Welcome!"); err != nil {
			return fmt.Errorf("welcome %s: %w", to, err)
		}
	}
	return nil
}

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

// HealthHandler answers every request with 200 OK and the body "ok".
func HealthHandler(w http.ResponseWriter, _ *http.Request) {
	_, _ = w.Write([]byte("ok")) // the client has gone if this fails; nothing to do
}

// CheckHealth calls the health endpoint at url and reports an error unless
// it answers 200 OK.
func CheckHealth(ctx context.Context, client *http.Client, url string) error {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return fmt.Errorf("check health: %w", err)
	}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("check health: %w", err)
	}
	defer resp.Body.Close() // read-only: a close error cannot lose data
	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("check health %s: status %d", url, resp.StatusCode)
	}
	return nil
}
