package project

// SystemConfigDir returns the directory for system-wide configuration. The
// build constraints on configdir_unix.go and configdir_other.go choose its
// implementation, so exactly one of them is compiled for any target.
func SystemConfigDir() string {
	return systemConfigDir()
}
