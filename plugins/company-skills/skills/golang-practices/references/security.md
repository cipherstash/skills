# Security

TLS verification, secrets, SQL, untrusted input, randomness, and the tools that find these problems.

The examples target Go 1.22, the `go` line in [`examples/go.mod`](../examples/go.mod). `filepath.IsLocal` needs Go 1.20, and `os.Root` needs Go 1.24, as the text says. Each Go example is quoted from the examples module, where tests check the behaviour the text describes.

## Contents

- [Rules](#rules)
- [Verify TLS certificates](#verify-tls-certificates)
- [Keep secrets out of source, logs, and errors](#keep-secrets-out-of-source-logs-and-errors)
- [Pass SQL values as arguments](#pass-sql-values-as-arguments)
- [Treat input as untrusted](#treat-input-as-untrusted)
- [Random values and comparisons](#random-values-and-comparisons)
- [Tools to run](#tools-to-run)

## Rules

- Never set `InsecureSkipVerify: true` outside a test. To trust a private certificate authority, add it to `RootCAs`.
- Never put a secret in source: no passwords, API keys, tokens, or private keys in code, tests, or committed config. Read them at run time from the environment or a secret store.
- Never log a secret or put one in an error message.
- Build SQL with placeholders and pass values as arguments. Never build it by concatenating or formatting input into the query text.
- Check every value from outside the process before use: paths, sizes, and anything placed in HTML, SQL, a shell, or a URL.
- Make tokens, keys, and nonces with `crypto/rand`, never `math/rand`. Compare secrets with `crypto/subtle.ConstantTimeCompare`.
- Run the security linter `gosec`, through `golangci-lint` where the repository uses it, and `govulncheck`. Explain each finding you suppress.

## Verify TLS certificates

Go's TLS client checks the server's certificate chain and host name by default. `InsecureSkipVerify: true` turns both checks off, so anyone on the network path can read and change the traffic. It is often added to get past a private certificate authority. Trust that authority instead:

From [`examples/security/tls.go`](../examples/security/tls.go):

```go
// NewClientWithCA returns an HTTP client that trusts the certificates in
// caPEM as well as the system roots. Use it for a server with a private
// certificate authority, instead of turning verification off.
func NewClientWithCA(caPEM []byte) (*http.Client, error) {
	pool, err := x509.SystemCertPool()
	if err != nil {
		pool = x509.NewCertPool() // no system pool on this platform: trust caPEM only
	}
	if !pool.AppendCertsFromPEM(caPEM) {
		return nil, errors.New("new client: no certificates found in CA PEM")
	}
	// Clone the default transport to keep its proxy settings, HTTP/2, and
	// timeouts. A bare &http.Transport{} has none of them. A program may have
	// replaced DefaultTransport with a wrapper, so check its type.
	base, ok := http.DefaultTransport.(*http.Transport)
	if !ok {
		return nil, fmt.Errorf("new client: http.DefaultTransport is %T, not *http.Transport", http.DefaultTransport)
	}
	transport := base.Clone()
	transport.TLSClientConfig = &tls.Config{
		RootCAs:    pool,
		MinVersion: tls.VersionTLS12,
		// InsecureSkipVerify stays false: certificates and host names are
		// checked.
	}
	return &http.Client{Timeout: 30 * time.Second, Transport: transport}, nil
}
```

- Start from a clone of `http.DefaultTransport` and change only `TLSClientConfig`. A program can replace it with a wrapper for tracing or tests. Check its type with the two-value form, and return an error when it is not an `*http.Transport`. A new `&http.Transport{}` ignores `HTTPS_PROXY` and `NO_PROXY`, has no dial, handshake, or idle timeouts, and, with a custom `TLSClientConfig`, does not use HTTP/2.
- Set `MinVersion: tls.VersionTLS12` or higher. Go's default minimum for clients has been TLS 1.2 since Go 1.18, but stating it guards against older toolchains and copied configs.
- Leave cipher suites at their defaults unless a policy requires otherwise; Go chooses safe ones.
- In tests, use `httptest.NewTLSServer` and its `Client()` instead of turning verification off. That client trusts the test certificate.
- Give HTTP servers timeouts. With no `ReadHeaderTimeout`, an `http.Server` lets a slow client keep a connection open indefinitely. `gosec` reports that.

## Keep secrets out of source, logs, and errors

A secret committed to a repository stays in its history after it is deleted. Every clone has a copy. If one is committed, treat it as leaked: rotate it, then remove it.

- Read secrets at start-up from the environment or a secret manager, into configuration that the program passes down. `LoadConfig` in `project-structure.md` does this.
- Keep test credentials obviously fake, and point tests at local services.
- Do not log configuration structs or requests whole. Log the fields you need. A type with a secret field can implement `String() string` and `LogValue() slog.Value` to print a placeholder.
- Name the setting in an error, not its value: `DATABASE_URL is required`, not the URL itself.

## Pass SQL values as arguments

A query built from input runs whatever that input contains. With placeholders, the driver sends the values separately from the SQL text, so a value can never change the query.

From [`examples/security/sql.go`](../examples/security/sql.go):

```go
// Execer is the part of *sql.DB and *sql.Tx that RenameUser needs.
type Execer interface {
	ExecContext(ctx context.Context, query string, args ...any) (sql.Result, error)
}

// RenameUser sets the name of user id. The values travel as arguments, never
// as part of the SQL text, so a name such as "x'; DROP TABLE users; --" is
// stored as text and not run. Placeholders are driver-specific: $1 for
// PostgreSQL, ? for MySQL and SQLite.
func RenameUser(ctx context.Context, db Execer, id int64, name string) error {
	if _, err := db.ExecContext(ctx, "UPDATE users SET name = $1 WHERE id = $2", name, id); err != nil {
		return fmt.Errorf("rename user %d: %w", id, err)
	}
	return nil
}
```

Never format or concatenate input into the query, as in `fmt.Sprintf("UPDATE users SET name = '%s' ...", name)`. A name containing a quote ends the string, and the rest of the name runs as SQL.

Placeholders work only for values. A table or column name, or a sort direction, cannot be a placeholder. Map the caller's choice onto a fixed list, so only strings from the source reach the query:

From [`examples/security/sql.go`](../examples/security/sql.go):

```go
// sortColumns maps the sort keys a caller may ask for to column names.
var sortColumns = map[string]string{
	"name":    "name",
	"created": "created_at",
}

// ListUsersQuery builds a query sorted by a caller-chosen column. Column
// names cannot be placeholders, so the key is checked against an allow-list
// and only a fixed string from the list reaches the SQL.
func ListUsersQuery(sortKey string) (string, error) {
	col, ok := sortColumns[sortKey]
	if !ok {
		return "", fmt.Errorf("list users: unknown sort key %q", sortKey)
	}
	return "SELECT id, name FROM users ORDER BY " + col, nil
}
```

Query builders and ORMs are safe only through their parameter APIs. A method that takes raw SQL text, such as a `Raw` or `Where` given a formatted string, is as unsafe as `fmt.Sprintf`.

## Treat input as untrusted

Anything from outside the process is untrusted. That includes request bodies, headers, query strings, and file names. It also includes environment variables set by others, and data that others can write to storage.

**File paths.** A file name such as `../../etc/passwd` can escape the directory it should stay in. Check it before joining:

From [`examples/security/input.go`](../examples/security/input.go):

```go
// OpenUpload opens the file name inside dir. It rejects absolute paths and
// paths with ".." that would leave dir, such as "../../etc/passwd".
// filepath.IsLocal needs Go 1.20. It checks the name only: a symbolic link
// inside dir can still point outside it. From Go 1.24, os.Root also stops
// that.
func OpenUpload(dir, name string) (*os.File, error) {
	if !filepath.IsLocal(name) {
		return nil, fmt.Errorf("open upload: %q is not a local path", name)
	}
	f, err := os.Open(filepath.Join(dir, name)) // #nosec G304 -- name is checked with filepath.IsLocal above
	if err != nil {
		return nil, fmt.Errorf("open upload: %w", err)
	}
	return f, nil
}
```

**Sizes.** Without a limit, one large request can exhaust memory. Cap request bodies with `http.MaxBytesReader`, and cap other readers with `io.LimitReader`. A `json.Decoder` reads one value and stops, so also check that nothing follows it, or a body such as `{"Name":"ada"} garbage` is accepted:

From [`examples/security/input.go`](../examples/security/input.go):

```go
// maxBodyBytes caps the size of a JSON request body.
const maxBodyBytes = 1 << 20 // 1 MiB

// DecodeJSON decodes the request body into v. It limits the body's size, so
// a client cannot exhaust memory, and rejects unknown fields and anything
// after the first JSON value.
func DecodeJSON(w http.ResponseWriter, r *http.Request, v any) error {
	dec := json.NewDecoder(http.MaxBytesReader(w, r.Body, maxBodyBytes))
	dec.DisallowUnknownFields()
	if err := dec.Decode(v); err != nil {
		return fmt.Errorf("decode request body: %w", err)
	}
	// Decode reads one value and leaves the rest. Only io.EOF shows there
	// was nothing after it. Keep any other error, such as
	// *http.MaxBytesError, so the caller can answer 413.
	switch err := dec.Decode(&struct{}{}); {
	case err == nil:
		return errors.New("decode request body: unexpected data after the JSON value")
	case !errors.Is(err, io.EOF):
		return fmt.Errorf("decode request body: %w", err)
	}
	return nil
}
```

**HTML.** Use `html/template` for HTML. It escapes each value for where it appears: element text, attribute, URL, or script. `text/template` escapes nothing. Converting input to `template.HTML` turns the escaping off, so do it only for HTML your program built.

From [`examples/security/input.go`](../examples/security/input.go):

```go
// greeting is parsed once. html/template escapes {{.}} for the context it
// appears in; text/template would not.
var greeting = template.Must(template.New("greeting").Parse(`<p>Hello, {{.}}!</p>`))

// WriteGreeting writes an HTML greeting for name, which may come from a user.
func WriteGreeting(w io.Writer, name string) error {
	if err := greeting.Execute(w, name); err != nil {
		return fmt.Errorf("write greeting: %w", err)
	}
	return nil
}
```

**Commands.** Run programs with `exec.CommandContext(ctx, "git", "log", "--", path)`, passing input as separate arguments. Never pass input to `sh -c`, where the shell interprets it. An argument that starts with `-` can still be read as an option, so put `--` before input where the program supports it.

**Redirects and URLs.** Check that a redirect target from a request is a relative path or an allowed host. Build URLs with `net/url` and `url.QueryEscape`, not string concatenation.

## Random values and comparisons

`math/rand` is predictable, so a token made with it can be guessed. Use `crypto/rand`. `==` on strings stops at the first differing byte, so how long it takes reveals how much of a guess was right. Compare secrets in constant time:

From [`examples/security/tokens.go`](../examples/security/tokens.go):

```go
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
```

Use MD5 (Message Digest 5) and SHA-1 only for checksums that face no attacker. Never use them for passwords or signatures. Hash passwords with a slow password hash such as bcrypt or argon2 (from `golang.org/x/crypto`), not a plain SHA-256.

## Tools to run

```sh
# Security lint. If the repository uses golangci-lint, enable gosec in its config and run:
golangci-lint run ./...
# Without golangci-lint:
go run github.com/securego/gosec/v2/cmd/gosec@latest ./...

# Known vulnerabilities in dependencies and the standard library. It reports first the ones the code calls:
go run golang.org/x/vuln/cmd/govulncheck@latest ./...
```

`gosec` finds the problems in this reference, among others. Its rule IDs for them:

| Rule | Problem |
| --- | --- |
| G402 | TLS verification skipped |
| G101 | Hard-coded credentials |
| G201, G202 | SQL built by formatting or concatenating strings |
| G304 | File path from input |
| G404 | `math/rand` used for secrets |
| G112 | HTTP server with no header timeout |

`gosec` also reports false positives. To suppress one, put `// #nosec G304 -- <reason>` on the line, naming the rule. Both `gosec` and golangci-lint honour it; `gosec` alone ignores `//nolint:gosec`.

A function that takes a path from its caller, such as a library's `WriteLines(path, ...)`, gets G304 although the caller owns the check. In test code, findings such as G304 on a golden-file path or G104 on `Close` are low risk; many repositories exclude `_test.go` files from `gosec` instead of suppressing each one.

`go run tool@latest` downloads and runs the latest release. Pin a version, or use the module's `tool` directive (Go 1.24), where the repository needs repeatable results. Updating dependencies after `govulncheck` reports one is in `dependencies.md`.
