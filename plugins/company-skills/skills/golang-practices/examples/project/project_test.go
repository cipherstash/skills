package project_test

import (
	"context"
	"errors"
	"runtime/debug"
	"strings"
	"testing"
	"time"

	"example.com/golang-practices/project"
)

type store struct{ err error }

func (s store) Create(context.Context, *project.User) error { return s.err }

func TestRegister(t *testing.T) {
	svc := project.NewUserService(store{}, func() string { return "u1" })
	u, err := svc.Register(context.Background(), "ada@example.com")
	if err != nil || u == nil || u.ID != "u1" || u.Email != "ada@example.com" {
		t.Fatalf("Register = %+v, %v", u, err)
	}

	boom := errors.New("db down")
	svc = project.NewUserService(store{err: boom}, func() string { return "u2" })
	u, err = svc.Register(context.Background(), "b@example.com")
	if u != nil || !errors.Is(err, boom) {
		t.Fatalf("Register = %+v, %v; want nil and an error wrapping %v", u, err, boom)
	}
}

func env(m map[string]string) func(string) (string, bool) {
	return func(k string) (string, bool) {
		v, ok := m[k]
		return v, ok
	}
}

func TestLoadConfig(t *testing.T) {
	cfg, err := project.LoadConfig(env(map[string]string{"DATABASE_URL": "postgres://db", "READ_TIMEOUT": "3s"}))
	if err != nil {
		t.Fatalf("LoadConfig: %v", err)
	}
	if cfg.Addr != ":8080" || cfg.ReadTimeout != 3*time.Second || cfg.DatabaseURL != "postgres://db" {
		t.Fatalf("cfg = %+v", cfg)
	}
}

func TestLoadConfigReportsEveryProblem(t *testing.T) {
	_, err := project.LoadConfig(env(map[string]string{"READ_TIMEOUT": "soon"}))
	if err == nil {
		t.Fatal("LoadConfig succeeded with a bad timeout and no database URL")
	}
	for _, want := range []string{"READ_TIMEOUT", "DATABASE_URL is required"} {
		if !strings.Contains(err.Error(), want) {
			t.Errorf("error %q does not mention %q", err, want)
		}
	}
}

func TestLoadConfigRejectsInvalidValues(t *testing.T) {
	for _, tt := range []struct {
		name, key, value string
	}{
		{"zero timeout", "READ_TIMEOUT", "0s"},
		{"negative timeout", "READ_TIMEOUT", "-5s"},
		{"empty address", "ADDR", ""},
	} {
		t.Run(tt.name, func(t *testing.T) {
			_, err := project.LoadConfig(env(map[string]string{tt.key: tt.value, "DATABASE_URL": "postgres://db"}))
			if err == nil {
				t.Fatalf("LoadConfig accepted %s=%q", tt.key, tt.value)
			}
			if !strings.Contains(err.Error(), tt.key) {
				t.Fatalf("error %q does not name %s", err, tt.key)
			}
		})
	}
}

func TestLoadConfigErrorsLeaveValuesOut(t *testing.T) {
	_, err := project.LoadConfig(env(map[string]string{"READ_TIMEOUT": "s3cr3t", "DATABASE_URL": "postgres://db"}))
	if err == nil {
		t.Fatal("LoadConfig accepted READ_TIMEOUT=s3cr3t")
	}
	if strings.Contains(err.Error(), "s3cr3t") {
		t.Fatalf("error %q contains the variable's value", err)
	}
}

var loadConfigErrors = map[string]bool{
	"ADDR is set but empty":                      true,
	"READ_TIMEOUT is not a duration such as 30s": true,
	"READ_TIMEOUT must be more than zero":        true,
	"DATABASE_URL is required":                   true,
}

// LoadConfig parses environment variables, so it has a Fuzz target.
func FuzzLoadConfig(f *testing.F) {
	f.Add(true, ":8080", true, "3s", true, "postgres://db")
	f.Add(true, "", true, "0s", true, "")
	f.Add(true, ":9090", true, "soon", true, "postgres://db")
	f.Add(false, "", false, "", true, "postgres://db")
	f.Fuzz(func(t *testing.T, setAddr bool, addr string, setTimeout bool, timeout string, setDB bool, dbURL string) {
		// A variable that is not set is left out of the map.
		vars := map[string]string{}
		if setAddr {
			vars["ADDR"] = addr
		}
		if setTimeout {
			vars["READ_TIMEOUT"] = timeout
		}
		if setDB {
			vars["DATABASE_URL"] = dbURL
		}
		cfg, err := project.LoadConfig(env(vars))
		if err != nil {
			// Errors leave the values out: each line is a fixed message.
			msgs, ok := strings.CutPrefix(err.Error(), "load config: ")
			if !ok {
				t.Fatalf("error %q does not start with load config:", err)
			}
			for _, msg := range strings.Split(msgs, "\n") {
				if !loadConfigErrors[msg] {
					t.Fatalf("error %q has the line %q, want only fixed messages", err, msg)
				}
			}
			return
		}
		if cfg.Addr == "" || cfg.ReadTimeout <= 0 || cfg.DatabaseURL == "" {
			t.Fatalf("LoadConfig(%q) = %+v with no error, want every setting valid", vars, cfg)
		}
		if !setAddr && cfg.Addr != ":8080" {
			t.Errorf("ADDR unset: Addr = %q, want the default :8080", cfg.Addr)
		}
		if !setTimeout && cfg.ReadTimeout != 10*time.Second {
			t.Errorf("READ_TIMEOUT unset: ReadTimeout = %v, want the default 10s", cfg.ReadTimeout)
		}
	})
}

func TestRevisionAndVersion(t *testing.T) {
	if project.Version != "dev" {
		t.Errorf("Version = %q, want the default dev without -ldflags", project.Version)
	}
	// A test binary records no vcs.revision, so Revision gives "unknown"
	// here. RevisionOf checks the lookup itself.
	if got := project.Revision(); got == "" {
		t.Error("Revision() is empty")
	}
	info := &debug.BuildInfo{Settings: []debug.BuildSetting{
		{Key: "vcs", Value: "git"},
		{Key: "vcs.revision", Value: "4f2a9c1"},
		{Key: "vcs.modified", Value: "false"},
	}}
	if got := project.RevisionOf(info); got != "4f2a9c1" {
		t.Errorf("RevisionOf(vcs.revision=4f2a9c1) = %q, want 4f2a9c1", got)
	}
	if got := project.RevisionOf(&debug.BuildInfo{}); got != "unknown" {
		t.Errorf("RevisionOf(no settings) = %q, want unknown", got)
	}
}
