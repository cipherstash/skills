package errorhandling_test

import (
	"testing"

	"example.com/golang-practices/errorhandling"
)

// ParsePort reads a string from outside the process, so it has a fuzz target.
// Plain go test runs the seeds; go test -fuzz=FuzzParsePort explores further.
func FuzzParsePort(f *testing.F) {
	for _, seed := range []string{"8080", "0", "65536", "-1", "+80", " 80", ""} {
		f.Add(seed)
	}
	f.Fuzz(func(t *testing.T, s string) {
		port, err := errorhandling.ParsePort(s)
		if err == nil && (port < 1 || port > 65535) {
			t.Fatalf("ParsePort(%q) = %d with no error, want a port in 1-65535", s, port)
		}
	})
}
