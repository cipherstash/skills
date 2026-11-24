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
	return RevisionOf(info)
}

// RevisionOf returns the revision recorded in info, or "unknown" if there is
// none. It also reads the build information of another binary, from
// debug/buildinfo.ReadFile.
func RevisionOf(info *debug.BuildInfo) string {
	for _, s := range info.Settings {
		if s.Key == "vcs.revision" {
			return s.Value
		}
	}
	return "unknown"
}
