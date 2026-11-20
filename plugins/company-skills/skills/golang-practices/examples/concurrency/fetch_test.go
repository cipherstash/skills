package concurrency_test

import (
	"context"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"example.com/golang-practices/concurrency"
)

func TestFetchReturnsTheBody(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.WriteString(w, "hello") // the test fails below if the write was lost
	}))
	defer srv.Close()

	body, err := concurrency.Fetch(context.Background(), srv.Client(), srv.URL)
	if err != nil {
		t.Fatalf("Fetch: %v", err)
	}
	if string(body) != "hello" {
		t.Fatalf("Fetch body = %q, want %q", body, "hello")
	}
}

func TestFetchStopsAtTheContextDeadline(t *testing.T) {
	// The server answers only when the client gives up, like a hung peer.
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		<-r.Context().Done()
	}))
	defer srv.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()
	start := time.Now()
	_, err := concurrency.Fetch(ctx, srv.Client(), srv.URL)
	if !errors.Is(err, context.DeadlineExceeded) {
		t.Fatalf("Fetch error = %v, want context.DeadlineExceeded", err)
	}
	if elapsed := time.Since(start); elapsed > prompt {
		t.Fatalf("Fetch took %v after its deadline", elapsed)
	}
}

func TestFetchReportsAnUnexpectedStatus(t *testing.T) {
	srv := httptest.NewServer(http.NotFoundHandler())
	defer srv.Close()

	_, err := concurrency.Fetch(context.Background(), srv.Client(), srv.URL)
	var statusErr *concurrency.StatusError
	if !errors.As(err, &statusErr) || statusErr.Code != http.StatusNotFound {
		t.Fatalf("Fetch error = %v, want a *StatusError with code 404", err)
	}
}
