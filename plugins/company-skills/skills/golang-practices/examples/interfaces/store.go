package interfaces

import (
	"context"
	"fmt"
)

// UserReader looks users up. With UserSaver, it splits storage by what
// callers use: a caller that only reads asks for a UserReader, and its fake
// needs one method.
type UserReader interface {
	User(ctx context.Context, id string) (User, error)
}

// UserStore is for the few callers that both read and save. It is composed
// from the small interfaces instead of repeating their methods.
type UserStore interface {
	UserReader
	UserSaver
}

// EmailOf returns the email address of the user with the given ID. It only
// reads, so it asks for a UserReader.
func EmailOf(ctx context.Context, users UserReader, id string) (string, error) {
	u, err := users.User(ctx, id)
	if err != nil {
		return "", fmt.Errorf("email of user %s: %w", id, err)
	}
	return u.Email, nil
}

// ChangeEmail reads a user, changes its email, and saves it. It needs both,
// so it asks for a UserStore.
func ChangeEmail(ctx context.Context, users UserStore, id, email string) error {
	u, err := users.User(ctx, id)
	if err != nil {
		return fmt.Errorf("change email of user %s: %w", id, err)
	}
	u.Email = email
	if err := users.SaveUser(ctx, u); err != nil {
		return fmt.Errorf("change email of user %s: %w", id, err)
	}
	return nil
}
