package interfaces

import (
	"context"
	"fmt"
)

// User is a registered user.
type User struct {
	ID    string
	Email string
}

// UserSaver is the one method Registrar needs from storage. It is defined
// here, where it is used, not beside the storage implementation, so the
// storage package does not need to know about it and tests can fake it with
// one method.
type UserSaver interface {
	SaveUser(ctx context.Context, u User) error
}

// Mailer sends email.
type Mailer interface {
	Send(ctx context.Context, to, subject, body string) error
}

// Registrar registers users. It accepts interfaces and is returned as a
// concrete type, so callers see every method it has.
type Registrar struct {
	users  UserSaver
	mailer Mailer
}

// NewRegistrar returns a Registrar that saves to users and sends with mailer.
func NewRegistrar(users UserSaver, mailer Mailer) *Registrar {
	return &Registrar{users: users, mailer: mailer}
}

// Register saves a user with the given ID and email and sends a welcome
// message.
func (r *Registrar) Register(ctx context.Context, id, email string) error {
	if err := r.users.SaveUser(ctx, User{ID: id, Email: email}); err != nil {
		return fmt.Errorf("register user %s: %w", id, err)
	}
	if err := r.mailer.Send(ctx, email, "Welcome", "Thanks for registering."); err != nil {
		return fmt.Errorf("register user %s: send welcome: %w", id, err)
	}
	return nil
}
