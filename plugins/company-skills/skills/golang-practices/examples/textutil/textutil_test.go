package textutil_test

import (
	"flag"
	"os"
	"path/filepath"
	"sync"
	"testing"
	"unicode/utf8"

	"example.com/golang-practices/textutil"
)

func TestReverse(t *testing.T) {
	tests := []struct {
		name string
		in   string
		want string
	}{
		{name: "empty", in: "", want: ""},
		{name: "one rune", in: "a", want: "a"},
		{name: "ascii", in: "hello", want: "olleh"},
		{name: "multi-byte runes", in: "héllo, 世界", want: "界世 ,olléh"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			// From Go 1.22 each iteration has its own tt, so the parallel
			// subtest sees the right case without a tt := tt copy.
			if got := textutil.Reverse(tt.in); got != tt.want {
				t.Errorf("Reverse(%q) = %q, want %q", tt.in, got, tt.want)
			}
		})
	}
}

func FuzzReverse(f *testing.F) {
	for _, seed := range []string{"", "hello", "héllo, 世界"} {
		f.Add(seed)
	}
	f.Fuzz(func(t *testing.T, s string) {
		if !utf8.ValidString(s) {
			t.Skip("Reverse is defined for valid UTF-8 only")
		}
		rev := textutil.Reverse(s)
		if !utf8.ValidString(rev) {
			t.Fatalf("Reverse(%q) = %q, which is not valid UTF-8", s, rev)
		}
		if again := textutil.Reverse(rev); again != s {
			t.Fatalf("Reverse(Reverse(%q)) = %q", s, again)
		}
	})
}

var update = flag.Bool("update", false, "rewrite golden files in testdata")

func TestRenderMatchesGoldenFile(t *testing.T) {
	got := textutil.Render("Fruit", []string{"apple", "pear"})
	golden := filepath.Join("testdata", "render.golden")

	if *update {
		if err := os.WriteFile(golden, []byte(got), 0o644); err != nil {
			t.Fatalf("update golden file: %v", err)
		}
	}
	want, err := os.ReadFile(golden)
	if err != nil {
		t.Fatalf("read golden file (run with -update to create it): %v", err)
	}
	if got != string(want) {
		t.Errorf("Render output differs from %s\ngot:\n%s\nwant:\n%s", golden, got, want)
	}
}

func TestCounterIsSafeForConcurrentUse(t *testing.T) {
	var c textutil.Counter
	var wg sync.WaitGroup
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			c.Inc()
		}()
	}
	wg.Wait()
	if got := c.Value(); got != 50 {
		t.Fatalf("Value() = %d, want 50", got)
	}
}
