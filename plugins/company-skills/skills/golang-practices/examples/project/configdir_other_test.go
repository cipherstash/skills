//go:build !unix

package project_test

import (
	"os"
	"path/filepath"
	"testing"

	"example.com/golang-practices/project"
)

// The build constraint matches configdir_other.go, so this expectation is
// checked on exactly the targets that compile that file.
func TestSystemConfigDir(t *testing.T) {
	want := filepath.Join(os.Getenv("ProgramData"), "example")
	if got := project.SystemConfigDir(); got != want {
		t.Fatalf("SystemConfigDir() = %q, want %q", got, want)
	}
}
