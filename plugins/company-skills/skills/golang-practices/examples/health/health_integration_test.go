//go:build integration

package health_test

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"example.com/golang-practices/health"
)

// TestCheckAgainstAServer runs only with -tags=integration. The build
// constraint is the first line of the file, followed by a blank line.
func TestCheckAgainstAServer(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(health.Handler))
	t.Cleanup(srv.Close) // ready as soon as NewServer returns: no sleep needed

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := health.Check(ctx, srv.Client(), srv.URL); err != nil {
		t.Fatalf("Check: %v", err)
	}
}
