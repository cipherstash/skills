package health

import (
	"context"
	"fmt"
	"net/http"
)

// Handler answers every request with 200 OK and the body "ok".
func Handler(w http.ResponseWriter, _ *http.Request) {
	_, _ = w.Write([]byte("ok")) // the client has gone if this fails; nothing to do
}

// Check calls the health endpoint at url and reports an error unless
// it answers 200 OK.
func Check(ctx context.Context, client *http.Client, url string) error {
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
