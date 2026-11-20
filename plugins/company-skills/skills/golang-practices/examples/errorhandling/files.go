package errorhandling

import (
	"errors"
	"fmt"
	"io"
	"os"
)

// WriteAll writes each line to w and then closes w. It reports a failed
// Close as well as a failed write: for a file, Close can be where a write
// error first shows up.
func WriteAll(w io.WriteCloser, lines []string) (err error) {
	defer func() {
		if cerr := w.Close(); cerr != nil {
			err = errors.Join(err, fmt.Errorf("close: %w", cerr))
		}
	}()
	for _, line := range lines {
		if _, err = fmt.Fprintln(w, line); err != nil {
			return fmt.Errorf("write line: %w", err)
		}
	}
	return nil
}

// WriteLines creates or truncates the file at path and writes lines to it.
func WriteLines(path string, lines []string) error {
	// Errors from *os.File methods are *fs.PathError values, which already
	// name the operation and the path, so the wrapping adds only what this
	// function was doing.
	f, err := os.Create(path) //nolint:gosec // G304: the caller chooses the path
	if err != nil {
		return fmt.Errorf("write lines: %w", err)
	}
	if err := WriteAll(f, lines); err != nil {
		return fmt.Errorf("write lines: %w", err)
	}
	return nil
}
