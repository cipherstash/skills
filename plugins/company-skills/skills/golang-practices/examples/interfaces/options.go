package interfaces

import "time"

// Server is configured with functional options.
type Server struct {
	addr     string
	timeout  time.Duration
	maxConns int
}

// Option configures a Server.
type Option func(*Server)

// WithAddr sets the address the server listens on.
func WithAddr(addr string) Option {
	return func(s *Server) { s.addr = addr }
}

// WithTimeout sets the per-request timeout.
func WithTimeout(d time.Duration) Option {
	return func(s *Server) { s.timeout = d }
}

// WithMaxConns sets the maximum number of open connections. The parameter is
// n, not max, so it does not shadow the built-in max function.
func WithMaxConns(n int) Option {
	return func(s *Server) { s.maxConns = n }
}

// NewServer returns a Server with defaults, changed by any options given.
func NewServer(opts ...Option) *Server {
	s := &Server{
		addr:     "localhost:8080",
		timeout:  30 * time.Second,
		maxConns: 100,
	}
	for _, opt := range opts {
		opt(s)
	}
	return s
}

// Addr returns the address the server listens on.
func (s *Server) Addr() string { return s.addr }

// Timeout returns the per-request timeout.
func (s *Server) Timeout() time.Duration { return s.timeout }

// MaxConns returns the maximum number of open connections.
func (s *Server) MaxConns() int { return s.maxConns }
