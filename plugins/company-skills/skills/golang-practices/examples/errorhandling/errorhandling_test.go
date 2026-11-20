package errorhandling_test

import (
	"errors"
	"io/fs"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"example.com/golang-practices/errorhandling"
)

func TestGreetingWrapsNotFoundWithContext(t *testing.T) {
	store := errorhandling.NewStore(map[int]string{1: "Ada"})

	got, err := errorhandling.Greeting(store, 1)
	if err != nil || got != "Hello, Ada" {
		t.Fatalf("Greeting(1) = %q, %v; want %q, nil", got, err, "Hello, Ada")
	}

	_, err = errorhandling.Greeting(store, 7)
	if want := "build greeting: user 7: not found"; err == nil || err.Error() != want {
		t.Fatalf("Greeting(7) error = %v, want %q", err, want)
	}
	if !errors.Is(err, errorhandling.ErrNotFound) {
		t.Fatalf("errors.Is(%v, ErrNotFound) = false, want true", err)
	}
	if err == errorhandling.ErrNotFound { // == compares identity and does not unwrap
		t.Fatal("a wrapped error compared equal to the sentinel; == should not see through wrapping")
	}
}

func TestParsePort(t *testing.T) {
	tests := []struct {
		name      string
		in        string
		want      int
		wantField string // set when a *ValidationError is expected
		wantIs    error  // set when errors.Is should match
	}{
		{name: "valid", in: "8080", want: 8080},
		{name: "not a number", in: "http", wantIs: strconv.ErrSyntax},
		{name: "out of range", in: "70000", wantField: "port"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := errorhandling.ParsePort(tt.in)
			switch {
			case tt.wantIs != nil:
				if !errors.Is(err, tt.wantIs) {
					t.Fatalf("ParsePort(%q) error = %v, want it to wrap %v", tt.in, err, tt.wantIs)
				}
			case tt.wantField != "":
				var verr *errorhandling.ValidationError
				if !errors.As(err, &verr) || verr.Field != tt.wantField {
					t.Fatalf("ParsePort(%q) error = %v, want a *ValidationError for %q", tt.in, err, tt.wantField)
				}
			default:
				if err != nil || got != tt.want {
					t.Fatalf("ParsePort(%q) = %d, %v; want %d, nil", tt.in, got, err, tt.want)
				}
			}
		})
	}
}

func TestValidateServerReportsEveryProblem(t *testing.T) {
	err := errorhandling.ValidateServer("", 0)
	if err == nil {
		t.Fatal("ValidateServer accepted an empty host and port 0")
	}
	for _, want := range []string{"host: is required", "port: must be between 1 and 65535"} {
		if !strings.Contains(err.Error(), want) {
			t.Errorf("ValidateServer error %q does not mention %q", err, want)
		}
	}
	var verr *errorhandling.ValidationError
	if !errors.As(err, &verr) {
		t.Fatalf("errors.As found no *ValidationError in %v", err)
	}
	if err := errorhandling.ValidateServer("db", 5432); err != nil {
		t.Fatalf("ValidateServer(valid) = %v, want nil", err)
	}
}

func TestTypedNilIsANonNilError(t *testing.T) {
	if err := errorhandling.CheckPortTypedNil(8080); err == nil {
		t.Fatal("the typed-nil example returned a nil error; the trap it shows has gone")
	}
	if err := errorhandling.CheckPort(8080); err != nil {
		t.Fatalf("CheckPort(8080) = %v, want nil", err)
	}
	if err := errorhandling.CheckPort(0); err == nil {
		t.Fatal("CheckPort(0) = nil, want an error")
	}
}

type fakeFile struct {
	writeErr, closeErr error
	closed             bool
	written            strings.Builder
}

func (f *fakeFile) Write(p []byte) (int, error) {
	if f.writeErr != nil {
		return 0, f.writeErr
	}
	return f.written.Write(p)
}

func (f *fakeFile) Close() error {
	f.closed = true
	return f.closeErr
}

func TestWriteAllReportsTheCloseError(t *testing.T) {
	errClose := errors.New("disk full")
	f := &fakeFile{closeErr: errClose}
	err := errorhandling.WriteAll(f, []string{"a"})
	if !errors.Is(err, errClose) {
		t.Fatalf("WriteAll error = %v, want it to wrap the close error", err)
	}
}

func TestWriteAllReportsWriteAndCloseErrors(t *testing.T) {
	errWrite := errors.New("write failed")
	errClose := errors.New("close failed")
	f := &fakeFile{writeErr: errWrite, closeErr: errClose}
	err := errorhandling.WriteAll(f, []string{"a"})
	if !errors.Is(err, errWrite) || !errors.Is(err, errClose) {
		t.Fatalf("WriteAll error = %v, want both the write and the close error", err)
	}
	if !f.closed {
		t.Fatal("WriteAll did not close the file after a write error")
	}
}

func TestWriteLines(t *testing.T) {
	path := filepath.Join(t.TempDir(), "out.txt")
	if err := errorhandling.WriteLines(path, []string{"a", "b"}); err != nil {
		t.Fatalf("WriteLines: %v", err)
	}
	got, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read back: %v", err)
	}
	if string(got) != "a\nb\n" {
		t.Fatalf("file = %q, want %q", got, "a\nb\n")
	}

	missing := filepath.Join(t.TempDir(), "no-such-dir", "out.txt")
	err = errorhandling.WriteLines(missing, nil)
	if !errors.Is(err, fs.ErrNotExist) {
		t.Fatalf("WriteLines into a missing directory = %v, want fs.ErrNotExist", err)
	}
	if strings.Count(err.Error(), missing) != 1 {
		t.Fatalf("error %q should name the path exactly once", err)
	}
}

func TestMustParsePortPanicsOnBadInput(t *testing.T) {
	if got := errorhandling.MustParsePort("443"); got != 443 {
		t.Fatalf("MustParsePort(443) = %d", got)
	}
	defer func() {
		if recover() == nil {
			t.Fatal("MustParsePort did not panic on bad input")
		}
	}()
	errorhandling.MustParsePort("not a port")
}

func TestRunSafelyTurnsAPanicIntoAnError(t *testing.T) {
	err := errorhandling.RunSafely(func() error {
		var m map[string]int
		m["boom"] = 1 // panics: assignment to entry in nil map
		return nil
	})
	var perr *errorhandling.PanicError
	if !errors.As(err, &perr) {
		t.Fatalf("RunSafely error = %v, want a *PanicError", err)
	}
	if len(perr.Stack) == 0 {
		t.Fatal("PanicError has no stack")
	}

	errPlain := errors.New("plain")
	if err := errorhandling.RunSafely(func() error { return errPlain }); err != errPlain {
		t.Fatalf("RunSafely passed through %v, want %v", err, errPlain)
	}
}
