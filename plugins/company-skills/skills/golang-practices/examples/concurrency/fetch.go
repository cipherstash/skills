package concurrency

import (
	"context"
	"fmt"
	"io"
	"net/http"
)

// StatusError reports a response whose status code was not 200 OK.
type StatusError struct {
	URL  string
	Code int
}

func (e *StatusError) Error() string {
	return fmt.Sprintf("get %s: unexpected status %d %s", e.URL, e.Code, http.StatusText(e.Code))
}

// Fetch returns the body of url. The request stops when ctx ends, so the
// caller sets the timeout:
//
//	ctx, cancel := context.WithTimeout(ctx, 5*time.Second)
//	defer cancel()
//	body, err := Fetch(ctx, http.DefaultClient, url)
func Fetch(ctx context.Context, client *http.Client, url string) ([]byte, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("build request for %s: %w", url, err)
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("get %s: %w", url, err)
	}
	defer resp.Body.Close() // read-only: a close error cannot lose data
	if resp.StatusCode != http.StatusOK {
		return nil, &StatusError{URL: url, Code: resp.StatusCode}
	}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read body of %s: %w", url, err)
	}
	return body, nil
}
