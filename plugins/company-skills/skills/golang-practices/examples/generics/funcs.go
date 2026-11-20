package generics

import (
	"cmp"
	"slices"
)

// Map returns a new slice holding fn applied to each element of s.
func Map[T, U any](s []T, fn func(T) U) []U {
	out := make([]U, 0, len(s))
	for _, v := range s {
		out = append(out, fn(v))
	}
	return out
}

// Filter returns a new slice holding the elements of s for which keep
// returns true.
func Filter[T any](s []T, keep func(T) bool) []T {
	var out []T
	for _, v := range s {
		if keep(v) {
			out = append(out, v)
		}
	}
	return out
}

// Reduce folds s into one value, starting from init.
func Reduce[T, A any](s []T, init A, fn func(A, T) A) A {
	acc := init
	for _, v := range s {
		acc = fn(acc, v)
	}
	return acc
}

// SortedKeys returns the keys of m in ascending order. Map iteration order is
// random, so sort keys before using them where order matters.
func SortedKeys[K cmp.Ordered, V any](m map[K]V) []K {
	keys := make([]K, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	slices.Sort(keys)
	return keys
}

// Clamp limits v to the range lo to hi. cmp.Ordered, from the standard
// library, allows any type that supports < and >. The built-in min and max
// functions (Go 1.21) do the comparisons, so there is no need to write or
// shadow them.
func Clamp[T cmp.Ordered](v, lo, hi T) T {
	return min(max(v, lo), hi)
}
