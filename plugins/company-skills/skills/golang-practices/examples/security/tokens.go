package security

import (
	"crypto/rand"
	"crypto/subtle"
	"encoding/base64"
	"fmt"
)

// NewToken returns a random 256-bit token, URL-safe base64 encoded. It uses
// crypto/rand: math/rand is predictable and must not make secrets.
func NewToken() (string, error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return "", fmt.Errorf("new token: %w", err)
	}
	return base64.RawURLEncoding.EncodeToString(b), nil
}

// TokenMatches compares a presented token with the expected one in constant
// time, so the time taken does not reveal how much of the token matched.
func TokenMatches(got, want string) bool {
	return subtle.ConstantTimeCompare([]byte(got), []byte(want)) == 1
}
