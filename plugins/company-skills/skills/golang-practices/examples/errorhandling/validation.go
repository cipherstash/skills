package errorhandling

import (
	"errors"
	"fmt"
	"strconv"
)

// ValidationError reports an invalid field. Match it with errors.As.
type ValidationError struct {
	Field   string
	Problem string
}

func (e *ValidationError) Error() string {
	return e.Field + ": " + e.Problem
}

// ParsePort parses s as a TCP port number.
func ParsePort(s string) (int, error) {
	n, err := strconv.Atoi(s)
	if err != nil {
		return 0, fmt.Errorf("parse port: %w", err)
	}
	if err := CheckPort(n); err != nil {
		return 0, err
	}
	return n, nil
}

// CheckPort reports whether port is a usable TCP port number.
func CheckPort(port int) error {
	if port < 1 || port > 65535 {
		return &ValidationError{Field: "port", Problem: "must be between 1 and 65535"}
	}
	return nil
}

// CheckPortTypedNil shows a mistake: it returns a nil *ValidationError as an
// error, and an interface holding a typed nil pointer is not nil. Callers
// see a failure for every port. Return the literal nil instead, as CheckPort
// does.
func CheckPortTypedNil(port int) error {
	var verr *ValidationError
	if port < 1 || port > 65535 {
		verr = &ValidationError{Field: "port", Problem: "must be between 1 and 65535"}
	}
	return verr // wrong: never a nil error
}

// ValidateServer reports every problem with host and port, not only the first.
func ValidateServer(host string, port int) error {
	var errs []error
	if host == "" {
		errs = append(errs, &ValidationError{Field: "host", Problem: "is required"})
	}
	if err := CheckPort(port); err != nil {
		errs = append(errs, err)
	}
	return errors.Join(errs...) // nil when errs is empty
}
