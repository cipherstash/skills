package health_test

import (
	"context"
	"net"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"

	"example.com/golang-practices/health"
)

func TestCheckReusesTheConnection(t *testing.T) {
	var opened atomic.Int32
	srv := httptest.NewUnstartedServer(http.HandlerFunc(health.Handler))
	srv.Config.ConnState = func(_ net.Conn, s http.ConnState) {
		if s == http.StateNew {
			opened.Add(1)
		}
	}
	srv.Start()
	t.Cleanup(srv.Close)

	for i := 0; i < 5; i++ {
		if err := health.Check(context.Background(), srv.Client(), srv.URL); err != nil {
			t.Fatalf("Check: %v", err)
		}
	}
	if n := opened.Load(); n != 1 {
		t.Fatalf("5 checks opened %d connections, want 1: the body was not drained", n)
	}
}

func TestCheckErrorHidesThePassword(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	t.Cleanup(srv.Close)

	url := strings.Replace(srv.URL, "http://", "http://user:s3cret@", 1)
	err := health.Check(context.Background(), srv.Client(), url)
	if err == nil {
		t.Fatal("Check returned no error for status 503")
	}
	if strings.Contains(err.Error(), "s3cret") {
		t.Fatalf("error contains the password: %v", err)
	}
}
