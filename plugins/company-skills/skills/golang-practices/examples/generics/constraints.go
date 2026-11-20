package generics

import (
	"fmt"
	"strings"
)

// Number is a constraint that allows any integer or floating-point type,
// including named types such as Celsius. A union (|) lists the types the
// constraint allows. ~float64 allows every type whose underlying type is
// float64, not only float64 itself.
type Number interface {
	~int | ~int8 | ~int16 | ~int32 | ~int64 |
		~uint | ~uint8 | ~uint16 | ~uint32 | ~uint64 | ~uintptr |
		~float32 | ~float64
}

// Sum adds the elements of s. The + operator is allowed because every type
// in Number supports it.
func Sum[T Number](s []T) T {
	var total T
	for _, v := range s {
		total += v
	}
	return total
}

// Celsius is a named type whose underlying type is float64, so it satisfies
// Number through ~float64.
type Celsius float64

// JoinStrings calls String on each element. A method constraint, here
// fmt.Stringer, is an ordinary interface used as a constraint.
func JoinStrings[T fmt.Stringer](items []T, sep string) string {
	parts := make([]string, 0, len(items))
	for _, item := range items {
		parts = append(parts, item.String())
	}
	return strings.Join(parts, sep)
}
