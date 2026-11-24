package welcome_test

import (
	"context"
	"errors"
	"testing"

	"example.com/golang-practices/welcome"
)

// fakeSender records what it is asked to send, and fails when err is set.
type fakeSender struct {
	err  error
	sent []string
}

func (f *fakeSender) Send(_ context.Context, to, _ string) error {
	if f.err != nil {
		return f.err
	}
	f.sent = append(f.sent, to)
	return nil
}

func TestWelcomeSendsToEachAddress(t *testing.T) {
	fake := &fakeSender{}
	if err := welcome.Welcome(context.Background(), fake, []string{"ada@example.com"}); err != nil {
		t.Fatalf("Welcome: %v", err)
	}
	if len(fake.sent) != 1 {
		t.Fatalf("sent %d messages, want 1", len(fake.sent)) // stop: fake.sent[0] would panic
	}
	if fake.sent[0] != "ada@example.com" {
		t.Errorf("sent to %q, want ada@example.com", fake.sent[0])
	}
}

func TestWelcomeWrapsTheSendError(t *testing.T) {
	boom := errors.New("smtp down")
	err := welcome.Welcome(context.Background(), &fakeSender{err: boom}, []string{"ada@example.com"})
	if !errors.Is(err, boom) {
		t.Fatalf("err = %v, want it to wrap %v", err, boom)
	}
}
