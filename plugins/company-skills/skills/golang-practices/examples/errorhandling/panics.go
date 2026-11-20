package errorhandling

import (
	"fmt"
	"runtime/debug"
)

// MustParsePort is ParsePort for values fixed in the source, such as a
// package-level default. It panics if s is not a valid port, because that is
// a bug in the program, not a runtime condition to handle.
func MustParsePort(s string) int {
	port, err := ParsePort(s)
	if err != nil {
		panic(fmt.Sprintf("MustParsePort(%q): %v", s, err))
	}
	return port
}

// defaultPort is checked once, at program start.
var defaultPort = MustParsePort("8080")

// DefaultPort returns the port used when none is configured.
func DefaultPort() int { return defaultPort }

// PanicError is a panic recovered by RunSafely.
type PanicError struct {
	Value any    // the value passed to panic
	Stack []byte // the panicking goroutine's stack
}

func (e *PanicError) Error() string {
	return fmt.Sprintf("panic: %v", e.Value)
}

// RunSafely calls fn and returns its error. If fn panics, RunSafely recovers
// and returns a *PanicError instead, so one failing task does not crash a
// long-running process. It only catches panics in the goroutine that calls
// it: a goroutine fn starts needs its own recover.
func RunSafely(fn func() error) (err error) {
	defer func() {
		if r := recover(); r != nil {
			err = &PanicError{Value: r, Stack: debug.Stack()}
		}
	}()
	return fn()
}
