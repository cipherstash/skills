package interfaces

import (
	"fmt"
	"io"
)

// UpperReader upper-cases the ASCII letters it reads from R. Other bytes,
// including UTF-8 sequences, pass through unchanged.
type UpperReader struct {
	R io.Reader
}

// Read reads from the underlying reader, then upper-cases the n bytes read.
// It returns the underlying reader's n and error unchanged, so io.EOF and
// short reads behave as the io.Reader contract says.
func (u *UpperReader) Read(p []byte) (int, error) {
	n, err := u.R.Read(p)
	for i, b := range p[:n] {
		if 'a' <= b && b <= 'z' {
			p[i] = b - ('a' - 'A')
		}
	}
	return n, err
}

// CountingWriter counts the bytes written through it to W.
type CountingWriter struct {
	W io.Writer
	N int64
}

// Write writes p to the underlying writer and adds the bytes it accepted,
// which may be fewer than len(p) on error, to N.
func (c *CountingWriter) Write(p []byte) (int, error) {
	n, err := c.W.Write(p)
	c.N += int64(n)
	return n, err
}

// Compile-time checks: the build fails if either type stops satisfying the
// interface, instead of a caller far away failing to compile.
var (
	_ io.Reader = (*UpperReader)(nil)
	_ io.Writer = (*CountingWriter)(nil)
)

// Flusher is implemented by writers that buffer, such as *bufio.Writer.
type Flusher interface {
	Flush() error
}

// WriteAndFlush writes data to w and, if w also buffers, flushes it.
func WriteAndFlush(w io.Writer, data []byte) error {
	if _, err := w.Write(data); err != nil {
		return fmt.Errorf("write: %w", err)
	}
	if f, ok := w.(Flusher); ok {
		if err := f.Flush(); err != nil {
			return fmt.Errorf("flush: %w", err)
		}
	}
	return nil
}
