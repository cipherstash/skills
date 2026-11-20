package interfaces

import "context"

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
