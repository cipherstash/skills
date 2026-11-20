package performance

import (
	"net/http"
	"net/http/pprof"
)

// DebugHandler serves the runtime profiles under /debug/pprof/. Serve it on
// its own listener bound to localhost, never on the public port: profiles
// reveal internals and can be expensive to produce. Importing net/http/pprof
// also registers these handlers on http.DefaultServeMux, so a service must
// not serve DefaultServeMux publicly either.
func DebugHandler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/debug/pprof/", pprof.Index)
	mux.HandleFunc("/debug/pprof/cmdline", pprof.Cmdline)
	mux.HandleFunc("/debug/pprof/profile", pprof.Profile)
	mux.HandleFunc("/debug/pprof/symbol", pprof.Symbol)
	mux.HandleFunc("/debug/pprof/trace", pprof.Trace)
	return mux
}
