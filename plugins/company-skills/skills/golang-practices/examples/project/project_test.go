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

// LoadConfig parses environment variables, so it has a Fuzz target.
func FuzzLoadConfig(f *testing.F) {
	f.Add(":8080", "3s", "postgres://db")
	f.Add("", "0s", "")
	f.Add(":9090", "soon", "postgres://db")
	f.Fuzz(func(t *testing.T, addr, timeout, dbURL string) {
		vars := map[string]string{"ADDR": addr, "READ_TIMEOUT": timeout, "DATABASE_URL": dbURL}
		cfg, err := project.LoadConfig(env(vars))
		if err != nil {
			return
		}
		if cfg.Addr == "" || cfg.ReadTimeout <= 0 || cfg.DatabaseURL == "" {
			t.Fatalf("LoadConfig(%q) = %+v with no error, want every setting valid", vars, cfg)
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
