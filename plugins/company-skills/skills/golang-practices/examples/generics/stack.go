package generics

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

// Len returns the number of items on the stack.
func (s *Stack[T]) Len() int { return len(s.items) }
