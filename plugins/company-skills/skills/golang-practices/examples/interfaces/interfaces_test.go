package interfaces_test

import (
	"bufio"
	"context"
	"errors"
	"io"
	"strings"
	"testing"
	"time"

	"example.com/golang-practices/interfaces"
)

func TestUpperReader(t *testing.T) {
	got, err := io.ReadAll(&interfaces.UpperReader{R: strings.NewReader("hello, wörld")})
	if err != nil {
		t.Fatalf("ReadAll: %v", err)
	}
	if want := "HELLO, WöRLD"; string(got) != want {
		t.Fatalf("got %q, want %q", got, want)
	}
}

func TestCountingWriter(t *testing.T) {
	var sb strings.Builder
	cw := &interfaces.CountingWriter{W: &sb}
	if _, err := io.WriteString(cw, "hello "); err != nil {
		t.Fatal(err)
	}
	if _, err := io.WriteString(cw, "world"); err != nil {
		t.Fatal(err)
	}
	if cw.N != 11 || sb.String() != "hello world" {
		t.Fatalf("N = %d, text = %q; want 11, %q", cw.N, sb.String(), "hello world")
	}
}

type failWriter struct{ err error }

func (f failWriter) Write([]byte) (int, error) { return 0, f.err }

func TestWriteAndFlush(t *testing.T) {
	var sb strings.Builder
	bw := bufio.NewWriter(&sb)
	if err := interfaces.WriteAndFlush(bw, []byte("data")); err != nil {
		t.Fatalf("WriteAndFlush: %v", err)
	}
	if sb.String() != "data" {
		t.Fatalf("buffered data was not flushed: got %q", sb.String())
	}

	// bufio.Writer reports a failing destination only when it flushes.
	boom := errors.New("disk full")
	err := interfaces.WriteAndFlush(bufio.NewWriter(failWriter{boom}), []byte("data"))
	if !errors.Is(err, boom) || !strings.HasPrefix(err.Error(), "flush: ") {
		t.Fatalf("err = %v, want a flush error wrapping %v", err, boom)
	}
}

func TestNewServerDefaultsAndOptions(t *testing.T) {
	s := interfaces.NewServer()
	if s.Addr() != "localhost:8080" || s.Timeout() != 30*time.Second || s.MaxConns() != 100 {
		t.Fatalf("defaults = %s, %v, %d", s.Addr(), s.Timeout(), s.MaxConns())
	}
	s = interfaces.NewServer(interfaces.WithAddr(":9000"), interfaces.WithTimeout(time.Second), interfaces.WithMaxConns(5))
	if s.Addr() != ":9000" || s.Timeout() != time.Second || s.MaxConns() != 5 {
		t.Fatalf("options = %s, %v, %d", s.Addr(), s.Timeout(), s.MaxConns())
	}
}

type fakeSaver struct {
	err   error
	saved []interfaces.User
}

func (f *fakeSaver) SaveUser(_ context.Context, u interfaces.User) error {
	if f.err != nil {
		return f.err
	}
	f.saved = append(f.saved, u)
	return nil
}

type fakeMailer struct {
	err error
	to  []string
}

func (f *fakeMailer) Send(_ context.Context, to, _, _ string) error {
	if f.err != nil {
		return f.err
	}
	f.to = append(f.to, to)
	return nil
}

func TestRegister(t *testing.T) {
	ctx := context.Background()
	saver, mailer := &fakeSaver{}, &fakeMailer{}
	r := interfaces.NewRegistrar(saver, mailer)
	if err := r.Register(ctx, "u1", "ada@example.com"); err != nil {
		t.Fatalf("Register: %v", err)
	}
	if len(saver.saved) != 1 || len(mailer.to) != 1 {
		t.Fatalf("saved %d users and sent %d emails, want 1 and 1", len(saver.saved), len(mailer.to))
	}

	dbErr := errors.New("connection refused")
	err := interfaces.NewRegistrar(&fakeSaver{err: dbErr}, mailer).Register(ctx, "u2", "b@example.com")
	if !errors.Is(err, dbErr) || err.Error() != "register user u2: connection refused" {
		t.Fatalf("err = %v, want it wrapped with the user ID", err)
	}

	mailErr := errors.New("smtp down")
	err = interfaces.NewRegistrar(&fakeSaver{}, &fakeMailer{err: mailErr}).Register(ctx, "u3", "c@example.com")
	if !errors.Is(err, mailErr) || err.Error() != "register user u3: send welcome: smtp down" {
		t.Fatalf("err = %v, want it wrapped with the step", err)
	}
}

type recorder struct{ msgs []string }

func (r *recorder) Log(msg string) { r.msgs = append(r.msgs, msg) }

func TestImporterLogs(t *testing.T) {
	rec := &recorder{}
	interfaces.NewImporter(rec).Import(3)
	if len(rec.msgs) != 1 || rec.msgs[0] != "imported 3 rows" {
		t.Fatalf("logged %q", rec.msgs)
	}
	interfaces.NewImporter(nil).Import(3) // must not panic on a nil logger
}

type celsius float64

func (c celsius) String() string { return "warm" }

func TestDescribe(t *testing.T) {
	tests := []struct {
		in   any
		want string
	}{
		{nil, "null"},
		{"hi", `"hi"`},
		{1.5, "1.5"},
		{true, "true"},
		{celsius(20), "warm"},
		{[]int{1}, "[]int"},
	}
	for _, tt := range tests {
		if got := interfaces.Describe(tt.in); got != tt.want {
			t.Errorf("Describe(%#v) = %q, want %q", tt.in, got, tt.want)
		}
	}
}
