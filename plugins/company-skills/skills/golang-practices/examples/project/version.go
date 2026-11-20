package project

import "runtime/debug"

// Version is set at build time:
//
//	go build -ldflags "-X example.com/golang-practices/project.Version=v1.2.3"
var Version = "dev"

// Revision returns the version control revision the binary was built from.
// go build records it from Go 1.18 when it runs inside a repository, so no
// -ldflags are needed for it.
func Revision() string {
	info, ok := debug.ReadBuildInfo()
	if !ok {
		return "unknown"
	}
	for _, s := range info.Settings {
		if s.Key == "vcs.revision" {
			return s.Value
		}
	}
	return "unknown"
}
