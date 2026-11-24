package errorhandling

import (
	"errors"
	"fmt"
)

// ErrNotFound is returned, wrapped, when a lookup finds nothing. Match it
// with errors.Is.
var ErrNotFound = errors.New("not found")

// Store is an in-memory user directory.
type Store struct {
	users map[int]string
}

// NewStore returns a Store holding users, keyed by ID.
func NewStore(users map[int]string) *Store {
	return &Store{users: users}
}

// Lookup returns the name of user id, or an error wrapping ErrNotFound.
func (s *Store) Lookup(id int) (string, error) {
	name, ok := s.users[id]
	if !ok {
		return "", fmt.Errorf("user %d: %w", id, ErrNotFound)
	}
	return name, nil
}

// Greeting returns a greeting for user id.
func Greeting(s *Store, id int) (string, error) {
	name, err := s.Lookup(id)
	if err != nil {
		return "", fmt.Errorf("build greeting: %w", err)
	}
	return "Hello, " + name, nil
}
