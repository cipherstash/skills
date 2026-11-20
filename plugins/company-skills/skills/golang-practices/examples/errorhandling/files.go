package errorhandling

import (
	"errors"
	"fmt"
	"io"
	"os"
)

// WriteAll writes each line to w and then closes w. It reports a failed
// Close as well as a failed write: for a file, Close can be where a write
// error first shows up. A file's errors are *fs.PathError values, which
// already name the operation and the path, so WriteAll adds only the number
// of the line that failed.
func WriteAll(w io.WriteCloser, lines []string) (err error) {
	defer func() {
		if cerr := w.Close(); cerr != nil {
			err = errors.Join(err, cerr)
		}
	}()
	for i, line := range lines {
		if _, err = fmt.Fprintln(w, line); err != nil {
			return fmt.Errorf("write line %d: %w", i+1, err)
		}
	}
	return nil
}

// WriteLines creates or truncates the file at path and writes lines to it.
func WriteLines(path string, lines []string) error {
	// Errors from *os.File methods are *fs.PathError values, which already
	// name the operation and the path, so the wrapping adds only what this
	// function was doing.
	f, err := os.Create(path)
	if err != nil {
		return fmt.Errorf("write lines: %w", err)
	}
	if err := WriteAll(f, lines); err != nil {
		return fmt.Errorf("write lines: %w", err)
	}
	return nil
}
