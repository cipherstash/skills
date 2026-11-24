package welcome

import (
	"context"
	"fmt"
)

// Sender sends a message to an address.
type Sender interface {
	Send(ctx context.Context, to, body string) error
}

// Welcome sends a welcome message to each address, stopping at the first
// failure.
func Welcome(ctx context.Context, s Sender, addrs []string) error {
	for _, to := range addrs {
		if err := s.Send(ctx, to, "Welcome!"); err != nil {
			return fmt.Errorf("welcome %s: %w", to, err)
		}
	}
	return nil
}
