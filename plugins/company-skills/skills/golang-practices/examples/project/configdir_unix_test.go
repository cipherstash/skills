//go:build unix

package project_test

import (
	"testing"

	"example.com/golang-practices/project"
)

// The build constraint matches configdir_unix.go, so this expectation is
// checked on exactly the targets that compile that file.
func TestSystemConfigDir(t *testing.T) {
	if got := project.SystemConfigDir(); got != "/etc/example" {
		t.Fatalf("SystemConfigDir() = %q, want /etc/example", got)
	}
}
