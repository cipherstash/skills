package project

import (
	"errors"
	"fmt"
	"time"
)

// Config is the service configuration.
type Config struct {
	Addr        string
	ReadTimeout time.Duration
	DatabaseURL string // a secret: never log it or put it in an error
}

// LoadConfig reads the configuration through lookup, which is os.LookupEnv
// in production and a map in tests. It reports every missing or invalid
// variable at once.
func LoadConfig(lookup func(string) (string, bool)) (Config, error) {
	cfg := Config{Addr: ":8080", ReadTimeout: 10 * time.Second}
	var errs []error

	if v, ok := lookup("ADDR"); ok {
		cfg.Addr = v
	}
	if v, ok := lookup("READ_TIMEOUT"); ok {
		d, err := time.ParseDuration(v)
		if err != nil {
			errs = append(errs, fmt.Errorf("READ_TIMEOUT: %w", err))
		}
		cfg.ReadTimeout = d
	}
	if v, ok := lookup("DATABASE_URL"); ok && v != "" {
		cfg.DatabaseURL = v
	} else {
		errs = append(errs, errors.New("DATABASE_URL is required"))
	}

	if err := errors.Join(errs...); err != nil {
		return Config{}, fmt.Errorf("load config: %w", err)
	}
	return cfg, nil
}
