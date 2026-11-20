//go:build !unix

package project

import (
	"os"
	"path/filepath"
)

// systemConfigDir is the directory for system-wide configuration on systems
// that are not Unix, such as Windows.
func systemConfigDir() string {
	return filepath.Join(os.Getenv("ProgramData"), "example")
}
