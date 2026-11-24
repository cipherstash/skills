package textutil

import (
	"fmt"
	"strings"
)

// Reverse returns s with its runes in reverse order. It works on runes, not
// bytes, so multi-byte UTF-8 characters stay intact.
func Reverse(s string) string {
	r := []rune(s)
	for i, j := 0, len(r)-1; i < j; i, j = i+1, j-1 {
		r[i], r[j] = r[j], r[i]
	}
	return string(r)
}

// Render formats a titled list, one item per line.
func Render(title string, items []string) string {
	var b strings.Builder
	fmt.Fprintf(&b, "# %s\n\n", title)
	for _, item := range items {
		fmt.Fprintf(&b, "- %s\n", item)
	}
	return b.String()
}
