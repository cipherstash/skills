# Generics

Type parameters, constraints, generic types, and generic channel stages.

The examples target Go 1.22, the `go` line in [`examples/go.mod`](../examples/go.mod). Type parameters need Go 1.18. The `cmp` and `slices` packages and the built-in `min` and `max` functions need Go 1.21. Each example is quoted from the examples module, where tests check the behaviour the text describes.

## Contents

- [Rules](#rules)
- [Choosing type parameters](#choosing-type-parameters)
- [Generic functions](#generic-functions)
- [Constraints](#constraints)
- [Generic types](#generic-types)
- [Generic channel stages](#generic-channel-stages)
- [Quick reference](#quick-reference)

## Rules

- Write a generic function when the same code would otherwise be copied for several types. Start with a concrete type or an interface, and add a type parameter when a second type needs the same code.
- Check the standard library first. `slices`, `maps`, and `cmp` (Go 1.21) cover sorting, searching, `Contains`, `Index`, `Max`, `Min`, `Equal`, and more.
- Use `cmp.Ordered` for types that support `<`. There is no `constraints` package in the standard library. `golang.org/x/exp/constraints` exists, but `cmp.Ordered` replaced its `Ordered`.
- Use the built-in `min` and `max` (Go 1.21). Do not define functions or variables named `min` or `max`: they shadow the built-ins.
- Use `comparable` for types used as map keys or with `==`.
- Return `(T, bool)` or `(T, error)` for "no value". Return `var zero T` as the value in that case.
- A goroutine inside a generic function follows the same rules as any other: it has a context or another way to stop. See `concurrency.md`.

## Choosing type parameters

Type parameters fit containers, such as a stack, a set, or a cache. They also fit functions over slices, maps, and channels whose code does not depend on the element type. An interface fits better when the code calls methods. `func Write(w io.Writer)` is simpler than `func Write[W io.Writer](w W)`, with the same effect.

Do not port patterns from other languages for their own sake. A generic `Result[T]` type, for example, fights Go's `(T, error)` convention, and every caller has to unwrap it.

## Generic functions

`Map`, `Filter`, and `Reduce` work on any element type. The compiler infers the type arguments from the arguments, so callers write `Map(ids, strconv.Itoa)` without `[int, string]`.

From [`examples/generics/funcs.go`](../examples/generics/funcs.go):

```go
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
```

Map iteration order is random. Sort the keys when order matters:

From [`examples/generics/funcs.go`](../examples/generics/funcs.go):

```go
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
```

`Clamp` uses the standard library's ordered constraint and the built-in `min` and `max`, so it needs no helpers of its own:

From [`examples/generics/funcs.go`](../examples/generics/funcs.go):

```go
// Clamp limits v to the range lo to hi. cmp.Ordered, from the standard
// library, allows any type that supports < and >. The built-in min and max
// functions (Go 1.21) do the comparisons, so there is no need to write or
// shadow them.
func Clamp[T cmp.Ordered](v, lo, hi T) T {
	return min(max(v, lo), hi)
}
```

## Constraints

A constraint is an interface. Like any interface, a constraint can list methods. A constraint can also list types in a union with `|`. A union says which types are allowed. Code can then use the operators those types share, such as `+` and `<`, on values of the type parameter.

`~T` allows every type whose underlying type is `T`. That includes named types such as `type Celsius float64`. Plain `float64` allows only `float64` itself. Named types are not aliases: `Celsius` is a distinct type with `float64` as its underlying type.

From [`examples/generics/constraints.go`](../examples/generics/constraints.go):

```go
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
```

From [`examples/generics/constraints.go`](../examples/generics/constraints.go):

```go
// Celsius is a named type whose underlying type is float64, so it satisfies
// Number through ~float64.
type Celsius float64
```

A union is a tool for when you need operators. It is not a requirement: `any`, `comparable`, `cmp.Ordered`, or an ordinary method interface is often enough. A constraint with methods works the same way as a parameter of interface type:

From [`examples/generics/constraints.go`](../examples/generics/constraints.go):

```go
// JoinStrings calls String on each element. A method constraint, here
// fmt.Stringer, is an ordinary interface used as a constraint.
func JoinStrings[T fmt.Stringer](items []T, sep string) string {
	parts := make([]string, 0, len(items))
	for _, item := range items {
		parts = append(parts, item.String())
	}
	return strings.Join(parts, sep)
}
```

A constraint that contains a union can only be used as a constraint. It cannot be the type of a variable or parameter.

## Generic types

A generic type takes its type parameters in its declaration, and its methods use them. Methods cannot have type parameters of their own.

From [`examples/generics/stack.go`](../examples/generics/stack.go):

```go
// Stack is a last-in, first-out stack. Its zero value is an empty stack.
type Stack[T any] struct {
	items []T
}

// Push adds v to the top of the stack.
func (s *Stack[T]) Push(v T) {
	s.items = append(s.items, v)
}

// Pop removes and returns the top of the stack. It returns the zero value
// and false when the stack is empty.
func (s *Stack[T]) Pop() (T, bool) {
	var zero T
	if len(s.items) == 0 {
		return zero, false
	}
	last := len(s.items) - 1
	v := s.items[last]
	s.items[last] = zero // drop the reference so the garbage collector can free it
	s.items = s.items[:last]
	return v, true
}
```

`Pop` clears the slot it removes. Without that, the backing array keeps a reference to the popped value, and the garbage collector cannot free it.

## Generic channel stages

A generic stage follows the concurrency rules: every receive and send also selects on `ctx.Done()`. So the goroutine stops when the context ends, even if its input is never closed or nobody reads its output.

From [`examples/generics/channels.go`](../examples/generics/channels.go):

```go
// Stage applies fn to each value from in and sends the result on the
// returned channel. It stops, and closes the returned channel, when in is
// closed or ctx ends, so it does not leak if the reader goes away.
func Stage[T, U any](ctx context.Context, in <-chan T, fn func(T) U) <-chan U {
	out := make(chan U)
	go func() {
		defer close(out)
		for {
			select {
			case <-ctx.Done():
				return
			case v, ok := <-in:
				if !ok {
					return
				}
				select {
				case out <- fn(v):
				case <-ctx.Done():
					return
				}
			}
		}
	}()
	return out
}
```

From [`examples/generics/channels.go`](../examples/generics/channels.go):

```go
// Merge sends every value from ins on one channel, which it closes once all
// of ins are closed or ctx ends.
func Merge[T any](ctx context.Context, ins ...<-chan T) <-chan T {
	out := make(chan T)
	var wg sync.WaitGroup
	wg.Add(len(ins))
	for _, in := range ins {
		go func(in <-chan T) {
			defer wg.Done()
			for {
				select {
				case <-ctx.Done():
					return
				case v, ok := <-in:
					if !ok {
						return
					}
					select {
					case out <- v:
					case <-ctx.Done():
						return
					}
				}
			}
		}(in)
	}
	go func() {
		wg.Wait()
		close(out)
	}()
	return out
}
```

`Merge` passes `in` to each goroutine as an argument. From Go 1.22 the loop variable is a new variable on each iteration, so capturing it directly would also be correct. The argument keeps the code correct when copied into a module on an older Go version.

## Quick reference

| Feature | Syntax | Notes |
| --- | --- | --- |
| Type parameter | `func F[T any](v T)` | `any` allows every type |
| Several parameters | `func F[K comparable, V any](m map[K]V)` | |
| Ordered types | `func F[T cmp.Ordered](a, b T)` | From `cmp`, Go 1.21. Allows `<`, `>`, `<=`, `>=` |
| Equality | `func F[T comparable](a, b T)` | Allows `==` and `!=` |
| Union | `interface{ ~int \| ~float64 }` | Lists allowed types; makes shared operators usable |
| Underlying type | `~float64` | Also allows named types whose underlying type is `float64` |
| Zero value | `var zero T` | Return with `false` or an error |
| Built-in min and max | `min(a, b)`, `max(a, b, c)` | Go 1.21; do not shadow them |
