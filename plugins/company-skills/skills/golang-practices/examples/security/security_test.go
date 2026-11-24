package security_test

import (
	"context"
	"database/sql"
	"encoding/pem"
	"errors"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"example.com/golang-practices/security"
)

func TestNewClientWithCATrustsThePrivateCA(t *testing.T) {
	srv := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusNoContent)
	}))
	defer srv.Close()

	// A client with the default roots refuses the test server's certificate.
	if _, err := http.Get(srv.URL); err == nil {
		t.Fatal("default client accepted a certificate from an unknown authority")
	}

	caPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: srv.Certificate().Raw})
	client, err := security.NewClientWithCA(caPEM)
	if err != nil {
		t.Fatalf("NewClientWithCA: %v", err)
	}
	resp, err := client.Get(srv.URL)
	if err != nil {
		t.Fatalf("GET with the CA trusted: %v", err)
	}
	resp.Body.Close()

	if _, err := security.NewClientWithCA([]byte("not a certificate")); err == nil {
		t.Fatal("NewClientWithCA accepted PEM with no certificates")
	}
}

func TestNewClientWithCAKeepsDefaultTransportSettings(t *testing.T) {
	srv := httptest.NewTLSServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	defer srv.Close()
	caPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: srv.Certificate().Raw})
	client, err := security.NewClientWithCA(caPEM)
	if err != nil {
		t.Fatalf("NewClientWithCA: %v", err)
	}
	tr, ok := client.Transport.(*http.Transport)
	if !ok {
		t.Fatalf("Transport is %T, want *http.Transport", client.Transport)
	}
	// A bare &http.Transport{} ignores HTTPS_PROXY and NO_PROXY, and a custom
	// TLSClientConfig turns HTTP/2 off unless ForceAttemptHTTP2 is set.
	if tr.Proxy == nil {
		t.Error("Transport.Proxy is nil: proxy environment variables are ignored")
	}
	if !tr.ForceAttemptHTTP2 {
		t.Error("Transport.ForceAttemptHTTP2 is false: HTTP/2 is off")
	}
	if tr.TLSHandshakeTimeout == 0 || tr.IdleConnTimeout == 0 {
		t.Errorf("Transport timeouts are unset: handshake %v, idle %v", tr.TLSHandshakeTimeout, tr.IdleConnTimeout)
	}
	if tr == http.DefaultTransport {
		t.Error("NewClientWithCA changed http.DefaultTransport instead of a clone")
	}
}

// wrappedTransport stands in for a tracing or recording RoundTripper that a
// program installs as http.DefaultTransport.
type wrappedTransport struct{ next http.RoundTripper }

func (w wrappedTransport) RoundTrip(r *http.Request) (*http.Response, error) {
	return w.next.RoundTrip(r)
}

// Not parallel: it replaces http.DefaultTransport for its duration.
func TestNewClientWithCAWithWrappedDefaultTransport(t *testing.T) {
	orig := http.DefaultTransport
	http.DefaultTransport = wrappedTransport{next: orig}
	t.Cleanup(func() { http.DefaultTransport = orig })

	srv := httptest.NewTLSServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	defer srv.Close()
	caPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: srv.Certificate().Raw})

	var err error
	func() {
		defer func() {
			if p := recover(); p != nil {
				t.Fatalf("NewClientWithCA panicked with a wrapped DefaultTransport: %v", p)
			}
		}()
		_, err = security.NewClientWithCA(caPEM)
	}()
	if err == nil {
		t.Fatal("NewClientWithCA returned no error when http.DefaultTransport is not an *http.Transport")
	}
}

type recordingExecer struct {
	query string
	args  []any
}

func (r *recordingExecer) ExecContext(_ context.Context, query string, args ...any) (sql.Result, error) {
	r.query, r.args = query, args
	return nil, nil
}

func TestRenameUserPassesValuesAsArguments(t *testing.T) {
	db := &recordingExecer{}
	name := "x'; DROP TABLE users; --"
	if err := security.RenameUser(context.Background(), db, 7, name); err != nil {
		t.Fatalf("RenameUser: %v", err)
	}
	if strings.Contains(db.query, name) {
		t.Fatalf("the name reached the SQL text: %q", db.query)
	}
	if len(db.args) != 2 || db.args[0] != name || db.args[1] != int64(7) {
		t.Fatalf("args = %#v", db.args)
	}
}

func TestListUsersQueryAllowsOnlyKnownColumns(t *testing.T) {
	q, err := security.ListUsersQuery("created")
	if err != nil || !strings.HasSuffix(q, "ORDER BY created_at") {
		t.Fatalf("ListUsersQuery(created) = %q, %v", q, err)
	}
	if _, err := security.ListUsersQuery("name; DROP TABLE users"); err == nil {
		t.Fatal("ListUsersQuery accepted an unknown sort key")
	}
}

func TestOpenUpload(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "a.txt"), []byte("a"), 0o600); err != nil {
		t.Fatal(err)
	}
	f, err := security.OpenUpload(dir, "a.txt")
	if err != nil {
		t.Fatalf("OpenUpload(a.txt): %v", err)
	}
	f.Close()

	for _, name := range []string{"../a.txt", "/etc/passwd", "sub/../../a.txt", ""} {
		if f, err := security.OpenUpload(dir, name); err == nil {
			f.Close()
			t.Errorf("OpenUpload(%q) succeeded, want it rejected", name)
		}
	}
}

func TestDecodeJSON(t *testing.T) {
	var v struct{ Name string }

	r := httptest.NewRequest(http.MethodPost, "/", strings.NewReader(`{"Name":"ada"}`))
	if err := security.DecodeJSON(httptest.NewRecorder(), r, &v); err != nil || v.Name != "ada" {
		t.Fatalf("DecodeJSON = %v, %+v", err, v)
	}

	r = httptest.NewRequest(http.MethodPost, "/", strings.NewReader(`{"Name":"ada","Admin":true}`))
	if err := security.DecodeJSON(httptest.NewRecorder(), r, &v); err == nil {
		t.Fatal("DecodeJSON accepted an unknown field")
	}

	for _, body := range []string{`{"Name":"ada"}{"Admin":true}`, `{"Name":"ada"} garbage`} {
		r = httptest.NewRequest(http.MethodPost, "/", strings.NewReader(body))
		if err := security.DecodeJSON(httptest.NewRecorder(), r, &v); err == nil {
			t.Errorf("DecodeJSON accepted trailing data in %s", body)
		}
	}

	r = httptest.NewRequest(http.MethodPost, "/", strings.NewReader("{\"Name\":\"ada\"}\n"))
	if err := security.DecodeJSON(httptest.NewRecorder(), r, &v); err != nil {
		t.Errorf("DecodeJSON rejected a body with a trailing newline: %v", err)
	}

	big := `{"Name":"` + strings.Repeat("a", 2<<20) + `"}`
	r = httptest.NewRequest(http.MethodPost, "/", strings.NewReader(big))
	var tooBig *http.MaxBytesError
	if err := security.DecodeJSON(httptest.NewRecorder(), r, &v); !errors.As(err, &tooBig) {
		t.Fatalf("DecodeJSON(2 MiB) error = %v, want *http.MaxBytesError", err)
	}

	// The limit can be hit after the first value, while looking for more.
	padded := `{"Name":"ada"}` + strings.Repeat(" ", 2<<20)
	r = httptest.NewRequest(http.MethodPost, "/", strings.NewReader(padded))
	if err := security.DecodeJSON(httptest.NewRecorder(), r, &v); !errors.As(err, &tooBig) {
		t.Fatalf("DecodeJSON(value + 2 MiB of spaces) error = %v, want *http.MaxBytesError", err)
	}
}

func TestWriteGreetingEscapesHTML(t *testing.T) {
	var b strings.Builder
	if err := security.WriteGreeting(&b, `<script>alert(1)</script>`); err != nil {
		t.Fatal(err)
	}
	if strings.Contains(b.String(), "<script>") {
		t.Fatalf("greeting was not escaped: %s", b.String())
	}
}

func TestTokens(t *testing.T) {
	a, err := security.NewToken()
	if err != nil {
		t.Fatal(err)
	}
	b, err := security.NewToken()
	if err != nil {
		t.Fatal(err)
	}
	if a == b || len(a) != 43 {
		t.Fatalf("tokens %q and %q: want two different 43-character tokens", a, b)
	}
	if !security.TokenMatches(a, a) || security.TokenMatches(a, b) {
		t.Fatal("TokenMatches gave the wrong answer")
	}
}

func TestRenameUserFormattedLetsInputChangeTheQuery(t *testing.T) {
	db := &recordingExecer{}
	if err := security.RenameUserFormatted(context.Background(), db, 7, "x'; DROP TABLE users; --"); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(db.query, "DROP TABLE users") {
		t.Fatalf("query = %q; this test pins the injection the example warns about", db.query)
	}
}
