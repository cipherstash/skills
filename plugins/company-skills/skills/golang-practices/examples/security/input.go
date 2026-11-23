package security

import (
	"encoding/json"
	"errors"
	"fmt"
	"html/template"
	"io"
	"net/http"
	"os"
	"path/filepath"
)

// OpenUpload opens the file name inside dir. It rejects absolute paths and
// paths with ".." that would leave dir, such as "../../etc/passwd".
// filepath.IsLocal needs Go 1.20. It checks the name only: a symbolic link
// inside dir can still point outside it. From Go 1.24, os.Root also stops
// that.
func OpenUpload(dir, name string) (*os.File, error) {
	if !filepath.IsLocal(name) {
		return nil, fmt.Errorf("open upload: %q is not a local path", name)
	}
	f, err := os.Open(filepath.Join(dir, name)) //nolint:gosec // G304: name is checked with filepath.IsLocal above
	if err != nil {
		return nil, fmt.Errorf("open upload: %w", err)
	}
	return f, nil
}

// maxBodyBytes caps the size of a JSON request body.
const maxBodyBytes = 1 << 20 // 1 MiB

// DecodeJSON decodes the request body into v. It limits the body's size, so
// a client cannot exhaust memory, and rejects unknown fields and anything
// after the first JSON value.
func DecodeJSON(w http.ResponseWriter, r *http.Request, v any) error {
	dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, maxBodyBytes))
	dec.DisallowUnknownFields()
	if err := dec.Decode(v); err != nil {
		return fmt.Errorf("decode request body: %w", err)
	}
	// Decode reads one value and leaves the rest. Only io.EOF shows there
	// was nothing after it.
	if err := dec.Decode(&struct{}{}); !errors.Is(err, io.EOF) {
		return errors.New("decode request body: unexpected data after the JSON value")
	}
	return nil
}

// greeting is parsed once. html/template escapes {{.}} for the context it
// appears in; text/template would not.
var greeting = template.Must(template.New("greeting").Parse(`<p>Hello, {{.}}!</p>`))

// WriteGreeting writes an HTML greeting for name, which may come from a user.
func WriteGreeting(w io.Writer, name string) error {
	if err := greeting.Execute(w, name); err != nil {
		return fmt.Errorf("write greeting: %w", err)
	}
	return nil
}
