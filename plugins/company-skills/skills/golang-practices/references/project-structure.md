# Project structure and modules

Laying out a module, naming packages and identifiers, `internal` packages, build constraints, configuration, build information, code generation, and container images. Adding and updating dependencies is in `dependencies.md`.

The examples target Go 1.22, the `go` line in [`examples/go.mod`](../examples/go.mod). The `//go:build` syntax needs Go 1.17, and the `unix` build constraint needs Go 1.19. The `tool` directive in `go.mod` needs Go 1.24, as the text says.

Each Go example is quoted from the examples module. The `go.mod`, layout, and Dockerfile blocks are illustrations. Nothing compiles them.

## Contents

- [Rules](#rules)
- [Layout](#layout)
- [Naming packages and identifiers](#naming-packages-and-identifiers)
- [Internal packages](#internal-packages)
- [The go.mod file](#the-gomod-file)
- [Workspaces](#workspaces)
- [Build constraints](#build-constraints)
- [Configuration](#configuration)
- [Build information](#build-information)
- [Code generation](#code-generation)
- [Container images](#container-images)

## Rules

- Start flat. Add directories when there are several binaries or a package grows a clear boundary, not up front.
- Put each binary's `main` package under `cmd/<name>/`, and keep it short: read configuration, build the dependencies, and run.
- Put code that other modules must not import under `internal/`.
- Name packages for what they provide, in short lower-case words. See [Naming packages and identifiers](#naming-packages-and-identifiers).
- A function returns a usable value or an error, not both: on error, return the zero value or `nil` with it. The exception is a partial result the contract documents, such as the `n` bytes that `io.Reader` and `io.Writer` return with an error.
- Read configuration once, at start-up, and pass it down. Report every missing or invalid setting together, and never put a secret in a log line or an error.
- Give each file at most one `//go:build` line, above the `package` clause and followed by a blank line.
- Commit `go.mod` and `go.sum`. Do not commit a `replace` that points at a path outside the repository.
- Build container images that run as a non-root user, from a current base image that matches the module's Go version.

## Layout

A small service:

```text
myservice/
├── go.mod
├── go.sum
├── cmd/
│   └── myservice/
│       └── main.go      # wiring only: config, dependencies, run
├── internal/
│   ├── user/            # one package per domain area
│   ├── store/           # database access
│   └── httpapi/         # HTTP handlers
└── testdata/            # fixtures for tests; ignored by the go tool's build
```

A library can be a single package at the module root. There is no official "standard layout": `pkg/` adds a path segment and protects nothing, so use it only if the repository already does. Directories such as `api/` (OpenAPI or protobuf files), `scripts/` and `deploy/` are fine when there is something to put in them.

## Naming packages and identifiers

**Packages**

- A package name is short, lower case, and one word, with no underscores or mixed caps: `user`, `httpapi`, `store`. The directory has the same name.
- Name it for what it provides. Avoid `util`, `common`, `helpers`, `misc`, `base`, and `models`. They say nothing, and unrelated code collects in them.
- Callers write the package name before every exported name, so do not repeat it: `user.Service`, not `user.UserService`; `config.Load`, not `config.LoadConfig`.

**Identifiers**

- Use `MixedCaps` for exported names and `mixedCaps` for unexported ones. Constants follow the same rule: `MaxRetries`, not `MAX_RETRIES`.
- Keep initialisms in one case: `ID`, `URL`, `HTTP`, `JSON`, `API`. Write `userID`, `baseURL`, `ServeHTTP`, `newHTTPClient`, not `userId`, `baseUrl`, or `ServeHttp`.
- Getters have no `Get` prefix: `Owner()`, with `SetOwner()` for the setter.
- Name error variables `ErrX` and error types `XError`.
- Name one-method interfaces with `-er`, or for their role: see `interfaces.md`.
- Short names for short scopes (`i`, `r`, `buf`), longer ones for package-level names.

**Receivers**

- A receiver is one or two letters taken from the type: `s` for `*UserService`, `c` for `*Client`.
- Use the same receiver name on every method of a type.
- Never `this` or `self`.

The service below follows these rules. Its receiver is `s` throughout. Its field is `ID`, not `Id`. Its `Register` returns the user or an error, never a half-made user alongside an error.

From [`examples/project/users.go`](../examples/project/users.go):

```go
// UserStore stores users.
type UserStore interface {
	Create(ctx context.Context, u *User) error
}

// UserService registers users. The ID generator and clock are fields so
// tests can fix them.
type UserService struct {
	store UserStore
	newID func() string
	now   func() time.Time
}

// NewUserService returns a UserService that stores users in store.
func NewUserService(store UserStore, newID func() string) *UserService {
	return &UserService{store: store, newID: newID, now: time.Now}
}

// Register creates a user with the given email. It returns the user, or nil
// and an error: never a half-made user alongside an error.
func (s *UserService) Register(ctx context.Context, email string) (*User, error) {
	u := &User{ID: s.newID(), Email: email, CreatedAt: s.now()}
	if err := s.store.Create(ctx, u); err != nil {
		return nil, fmt.Errorf("register %s: %w", email, err)
	}
	return u, nil
}
```

## Internal packages

A package under a directory named `internal` can be imported only by code rooted at the parent of `internal`. In `github.com/acme/myservice`, `internal/user` can be imported by any package in `myservice`, and by nothing outside it. `myservice/api/internal/codec` can be imported only from `myservice/api` and below. The go tool enforces this.

Put everything in `internal/` that is not meant as a public API. Code moved out of `internal/` later becomes public. Code exported from a public package has to stay compatible.

## The go.mod file

```text
module github.com/acme/myservice

go 1.22

require (
	github.com/lib/pq v1.10.9
)

require golang.org/x/sys v0.20.0 // indirect
```

- `module` is the import path of the module's root package.
- `go` is the minimum Go version for the module. It also sets the language rules the module is compiled with, such as the Go 1.22 loop variable semantics. From Go 1.21, a go command older than this line does not build the module. It downloads a newer toolchain instead, when the `GOTOOLCHAIN` setting allows that. Read this line before applying a version-sensitive rule.
- `toolchain` (Go 1.21 and later), when present, names the toolchain to use if the local one is older.
- `require` lists direct dependencies. Entries marked `// indirect` are needed by dependencies; `go mod tidy` maintains them.
- `replace` with a path outside the repository (`=> ../mylib`) is for local development only. A `go.work` file does the same without editing `go.mod`.
- `retract` marks versions of your own module that users should not pick.

## Workspaces

A workspace (Go 1.18) builds several modules in one repository together, using the local copies instead of published versions:

```text
go 1.22

use (
	./services/api
	./services/worker
	./shared/models
)
```

Create it with `go work init ./services/api ./services/worker` and add modules with `go work use <dir>`. Many projects leave `go.work` out of version control, so CI builds each module against its declared dependencies. Follow the repository's practice. Set `GOWORK=off` to build without the workspace.

## Build constraints

A build constraint chooses the files compiled for a target.

Each file has at most one `//go:build` line. It comes before the `package` clause, with only blank lines and other `//` comments, such as a licence header, above it, and it is followed by a blank line. It combines conditions with `&&`, `||`, `!`, and parentheses. Two `//go:build` lines in one file is an error. The old `// +build` lines are not needed from Go 1.17.

Split code that differs by platform into files whose constraints cover every target exactly once. Here `unix` (Go 1.19) and `!unix` do that:

From [`examples/project/configdir_unix.go`](../examples/project/configdir_unix.go):

```go
//go:build unix

package project

// systemConfigDir is the directory for system-wide configuration on Unix
// systems, including Linux and macOS.
func systemConfigDir() string {
	return "/etc/example"
}
```

From [`examples/project/configdir_other.go`](../examples/project/configdir_other.go):

```go
//go:build !unix

package project

import (
	"os"
	"path/filepath"
)

// systemConfigDir is the directory for system-wide configuration on systems
// that are not Unix, such as Windows.
func systemConfigDir() string {
	return filepath.Join(os.Getenv("ProgramData"), "example")
}
```

A file name that ends in `_linux.go`, `_windows.go`, `_arm64.go`, or `_linux_arm64.go` has an implied constraint, with no `//go:build` line. Tests behind a custom tag, such as `integration`, are in `testing.md`.

To check every variant compiles, vet for another target: `GOOS=windows go vet ./...`.

## Configuration

Read settings once at start-up, into a struct the program passes down. They can come from the environment, flags, or a file. Taking the lookup function as a parameter lets tests use a map instead of changing the process environment.

From [`examples/project/config.go`](../examples/project/config.go):

```go
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
			// time.ParseDuration's error quotes the value. Leave it out, as
			// for any setting that might hold a secret.
			errs = append(errs, errors.New("READ_TIMEOUT is not a duration such as 30s"))
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
```

`LoadConfig` reports every problem together with `errors.Join`, and its errors name the variable, not its value, so a secret cannot leak into a log. That is why it does not wrap `time.ParseDuration`'s error, which quotes the value. Call it as `project.LoadConfig(os.LookupEnv)`.

## Build information

From Go 1.18, `go build` inside a version-control checkout records the revision, its time, and whether the tree was modified. `runtime/debug.ReadBuildInfo` reads them, and `go version -m <binary>` prints them. Set a release version with `-ldflags "-X"`.

From [`examples/project/version.go`](../examples/project/version.go):

```go
// Version is set at build time:
//
//	go build -ldflags "-X example.com/golang-practices/project.Version=v1.2.3"
var Version = "dev"

// Revision returns the version control revision the binary was built from.
// go build records it from Go 1.18 when it runs inside a repository, so no
// -ldflags are needed for it.
func Revision() string {
	info, ok := debug.ReadBuildInfo()
	if !ok {
		return "unknown"
	}
	for _, s := range info.Settings {
		if s.Key == "vcs.revision" {
			return s.Value
		}
	}
	return "unknown"
}
```

## Code generation

`go generate ./...` runs the commands in `//go:generate` comments, such as `//go:generate stringer -type=State`. It is not run by `go build` or `go test`; commit the generated files and run it again when their inputs change. Generated files start with a line matching `// Code generated ... DO NOT EDIT.`. Linters and reviewers skip files with that line.

Track the generator's version in `go.mod`, so everyone runs the same one:

- From Go 1.24: `go get -tool golang.org/x/tools/cmd/stringer` adds a `tool` directive, and `go tool stringer` runs it.
- Before Go 1.24: a `tools.go` file with `//go:build tools` that blank-imports the tool's package, so `go mod tidy` keeps it in `go.mod`. Run it with `go run golang.org/x/tools/cmd/stringer`.

For mocks, see "Fakes instead of mocking libraries" in `testing.md`. `github.com/golang/mock` is archived; use `go.uber.org/mock` if a project already generates mocks.

## Container images

Build in one stage and copy the binary into a small runtime image that runs as a non-root user:

```dockerfile
# GO_VERSION: the latest supported Go release, and at least the go line in go.mod.
# Pin images by digest in production.
ARG GO_VERSION
FROM golang:${GO_VERSION}-bookworm AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -trimpath -o /out/myservice ./cmd/myservice

# distroless/static includes CA certificates and a nonroot user, and no shell.
FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/myservice /myservice
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/myservice"]
```

- Do not run as root. If the runtime image has no non-root user, create one and switch to it with `USER`.
- Do not use `latest` for base images, and do not hard-code an old Go version. Build with the latest supported Go release, passed as `--build-arg GO_VERSION=<version>` or set as the `ARG` default. Go supports only the two newest major releases, and each minor release carries security fixes for the standard library, which is compiled into the binary. Update the version when a new Go release comes out, not only when `go.mod` moves.
- `CGO_ENABLED=0` builds a static binary that needs no C library. A program that uses cgo needs a runtime image with the matching C library, such as `distroless/base`.
- `-trimpath` removes local file paths from the binary.
- Copy only the binary and the files it reads, never the source tree, `.git`, or secrets. Add a `.dockerignore`.
