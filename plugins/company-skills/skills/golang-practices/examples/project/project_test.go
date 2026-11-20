package project_test

import (
	"context"
	"errors"
	"runtime"
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

func TestLoadConfigErrorsLeaveValuesOut(t *testing.T) {
	_, err := project.LoadConfig(env(map[string]string{"READ_TIMEOUT": "s3cr3t", "DATABASE_URL": "postgres://db"}))
	if err == nil {
		t.Fatal("LoadConfig accepted READ_TIMEOUT=s3cr3t")
	}
	if strings.Contains(err.Error(), "s3cr3t") {
		t.Fatalf("error %q contains the variable's value", err)
	}
}

func TestRevisionAndVersion(t *testing.T) {
	if project.Version != "dev" {
		t.Errorf("Version = %q, want the default dev without -ldflags", project.Version)
	}
	if project.Revision() == "" {
		t.Error("Revision() is empty")
	}
}

func TestSystemConfigDir(t *testing.T) {
	got := project.SystemConfigDir()
	if runtime.GOOS != "windows" && got != "/etc/example" {
		t.Fatalf("SystemConfigDir() = %q on %s", got, runtime.GOOS)
	}
}
