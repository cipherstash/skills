//go:build unix

package project

// systemConfigDir is the directory for system-wide configuration on Unix
// systems, including Linux and macOS.
func systemConfigDir() string {
	return "/etc/example"
}
