package performance_test

import (
	"fmt"
	"net/http"
	"net/http/httptest"
	"slices"
	"testing"

	"example.com/golang-practices/performance"
)

func users(n int) []performance.User {
	out := make([]performance.User, 0, n)
	for i := 0; i < n; i++ {
		out = append(out, performance.User{ID: int64(i), Name: fmt.Sprintf("user%d", i)})
	}
	return out
}

func TestResults(t *testing.T) {
	us := users(3)
	if got := performance.IDs(us); !slices.Equal(got, []int64{0, 1, 2}) {
		t.Errorf("IDs = %v", got)
	}
	if got := performance.ByID(us); len(got) != 3 || got[2].Name != "user2" {
		t.Errorf("ByID = %v", got)
	}
	want := "user0,user1,user2"
	if got := performance.JoinNames(us); got != want {
		t.Errorf("JoinNames = %q", got)
	}
	if got := performance.JoinNamesConcat(us); got != want {
		t.Errorf("JoinNamesConcat = %q", got)
	}
	var buf []byte
	for _, u := range us[:2] {
		buf = performance.AppendCSV(buf, u)
	}
	if got := string(buf); got != "0,user0\n1,user1\n" {
		t.Errorf("AppendCSV = %q", got)
	}
}

// sink keeps results alive so the compiler cannot remove the work being
// measured.
var sink string

func BenchmarkJoinNames(b *testing.B) {
	us := users(1000) // setup, before the timer starts
	b.Run("concat", func(b *testing.B) {
		b.ReportAllocs()
		for i := 0; i < b.N; i++ {
			sink = performance.JoinNamesConcat(us)
		}
	})
	b.Run("builder", func(b *testing.B) {
		b.ReportAllocs()
		for i := 0; i < b.N; i++ {
			sink = performance.JoinNames(us)
		}
	})
}

func BenchmarkAppendCSV(b *testing.B) {
	us := users(1000)
	buf := make([]byte, 0, 64*1024)
	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		buf = buf[:0] // reuse the buffer: no allocation once it is big enough
		for _, u := range us {
			buf = performance.AppendCSV(buf, u)
		}
	}
}

func TestDebugHandlerServesProfiles(t *testing.T) {
	srv := httptest.NewServer(performance.DebugHandler())
	defer srv.Close()
	for _, path := range []string{"/debug/pprof/", "/debug/pprof/goroutine?debug=1", "/debug/pprof/heap"} {
		resp, err := srv.Client().Get(srv.URL + path)
		if err != nil {
			t.Fatalf("GET %s: %v", path, err)
		}
		resp.Body.Close()
		if resp.StatusCode != http.StatusOK {
			t.Errorf("GET %s: status %d", path, resp.StatusCode)
		}
	}
}
