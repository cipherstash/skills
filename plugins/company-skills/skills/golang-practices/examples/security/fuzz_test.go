package security_test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"example.com/golang-practices/security"
)

// OpenUpload and DecodeJSON take input from a client, so each has a fuzz
// target. Plain go test runs the seeds; go test -fuzz=<name> explores further.

func FuzzOpenUpload(f *testing.F) {
	for _, seed := range []string{"a.txt", "../secret.txt", "/etc/passwd", "sub/../a.txt", ""} {
		f.Add(seed)
	}
	root := f.TempDir()
	dir := filepath.Join(root, "uploads")
	if err := os.Mkdir(dir, 0o700); err != nil {
		f.Fatal(err)
	}
	for _, p := range []string{filepath.Join(dir, "a.txt"), filepath.Join(root, "secret.txt")} {
		if err := os.WriteFile(p, []byte("x"), 0o600); err != nil {
			f.Fatal(err)
		}
	}
	f.Fuzz(func(t *testing.T, name string) {
		file, err := security.OpenUpload(dir, name)
		if err != nil {
			return
		}
		defer func() { _ = file.Close() }()
		rel, err := filepath.Rel(dir, file.Name())
		if err != nil || !filepath.IsLocal(rel) {
			t.Fatalf("OpenUpload(%q) opened %s, outside %s", name, file.Name(), dir)
		}
	})
}

func FuzzDecodeJSON(f *testing.F) {
	for _, seed := range []string{`{"Name":"ada"}`, `{"Name":"ada"} garbage`, `{"Admin":true}`, `[]`, ``} {
		f.Add(seed)
	}
	f.Fuzz(func(t *testing.T, body string) {
		var v struct{ Name string }
		r := httptest.NewRequest(http.MethodPost, "/", strings.NewReader(body))
		if err := security.DecodeJSON(httptest.NewRecorder(), r, &v); err != nil {
			return
		}
		if !json.Valid([]byte(body)) {
			t.Fatalf("DecodeJSON accepted %q, which is not one JSON value", body)
		}
	})
}
