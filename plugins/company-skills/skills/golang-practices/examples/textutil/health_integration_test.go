//go:build integration

package textutil_test

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"example.com/golang-practices/textutil"
)

// TestCheckHealthAgainstAServer runs only with -tags=integration. The build
// constraint is the first line of the file, followed by a blank line.
func TestCheckHealthAgainstAServer(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(textutil.HealthHandler))
	t.Cleanup(srv.Close) // ready as soon as NewServer returns: no sleep needed

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	if err := textutil.CheckHealth(ctx, srv.Client(), srv.URL); err != nil {
		t.Fatalf("CheckHealth: %v", err)
	}
}
