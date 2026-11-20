package textutil_test

import (
	"os"
	"path/filepath"
	"testing"
)

// writeFixture writes content to a file in a fresh temporary directory and
// returns its path. t.Helper makes a failure point at the caller's line, and
// t.TempDir removes the directory when the test ends.
func writeFixture(t *testing.T, name, content string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), name)
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("write fixture %s: %v", name, err)
	}
	return path
}

func TestWriteFixture(t *testing.T) {
	path := writeFixture(t, "in.txt", "hello")
	got, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read fixture: %v", err)
	}
	if string(got) != "hello" {
		t.Fatalf("fixture holds %q, want %q", got, "hello")
	}
}
