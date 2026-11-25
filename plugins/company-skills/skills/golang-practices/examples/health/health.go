package health

import (
	"context"
	"fmt"
	"io"
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
	// Read what is left of the body, up to a limit, so the connection goes
	// back to the pool. Closing an unread body closes the connection.
	_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, 4<<10))
	if resp.StatusCode != http.StatusOK {
		// Redacted hides a password in the URL.
		return fmt.Errorf("check health %s: status %d", req.URL.Redacted(), resp.StatusCode)
	}
	return nil
}
