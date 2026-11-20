package project

import (
	"context"
	"fmt"
	"time"
)

// User is a registered user.
type User struct {
	ID        string
	Email     string
	CreatedAt time.Time
}

// UserStore stores users.
type UserStore interface {
	Create(ctx context.Context, u *User) error
}

// UserService registers users. The ID generator and clock are fields so
// tests can fix them.
type UserService struct {
	store UserStore
	newID func() string
	now   func() time.Time
}

// NewUserService returns a UserService that stores users in store.
func NewUserService(store UserStore, newID func() string) *UserService {
	return &UserService{store: store, newID: newID, now: time.Now}
}

// Register creates a user with the given email. It returns the user, or nil
// and an error: never a half-made user alongside an error.
func (s *UserService) Register(ctx context.Context, email string) (*User, error) {
	u := &User{ID: s.newID(), Email: email, CreatedAt: s.now()}
	if err := s.store.Create(ctx, u); err != nil {
		return nil, fmt.Errorf("register %s: %w", email, err)
	}
	return u, nil
}
