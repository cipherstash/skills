# Interfaces

Designing interfaces, implementing `io.Reader` and `io.Writer`, embedding, functional options, and type assertions.

The examples target Go 1.22, the `go` line in [`examples/go.mod`](../examples/go.mod). Nothing here needs a version later than Go 1.18, where `any` became an alias for `interface{}`. Each example is quoted from the examples module, where tests check the behaviour the text describes.

## Contents

- [Rules](#rules)
- [Define small interfaces where they are used](#define-small-interfaces-where-they-are-used)
- [Implement io.Reader and io.Writer](#implement-ioreader-and-iowriter)
- [Check optional methods with a type assertion](#check-optional-methods-with-a-type-assertion)
- [Embedding](#embedding)
- [Functional options](#functional-options)
- [Type switches](#type-switches)
- [Pointer and value receivers](#pointer-and-value-receivers)
- [Quick reference](#quick-reference)

## Rules

- Define an interface in the package that uses it, with only the methods that package calls. Do not define one beside its only implementation "for mocking".
- Keep interfaces small. One or two methods is common. Compose bigger ones from small ones (`io.ReadWriteCloser` is `io.Reader`, `io.Writer`, and `io.Closer`).
- Accept interfaces, return concrete types. A constructor returns `*T`, so callers see every method and the type can grow without breaking them. Return an interface only when the concrete type must stay hidden, as `errors.New` does.
- Name a one-method interface after its method plus `-er`: `Reader`, `Closer`, `Flusher`. Do not prefix with `I` or suffix with `Interface`.
- Use the two-value type assertion, `v, ok := x.(T)`, unless a failed assertion is a bug. The one-value form panics.
- Wrap errors that an implementation returns from the calls it makes, as in any other function. See `error-handling.md`. The exception is an error the interface's contract names, such as `io.EOF` from a `Read`: return it unwrapped, because callers compare it with `==`.
- Add a compile-time check, `var _ io.Reader = (*T)(nil)`, when a type is meant to satisfy an interface that nothing in its own package uses.

## Define small interfaces where they are used

`Registrar` needs to save a user and send an email, so it defines two small interfaces with just those methods. The storage package does not import them or know they exist: any type with a matching `SaveUser` method satisfies `UserSaver`. A test fakes each with a few lines.

From [`examples/interfaces/users.go`](../examples/interfaces/users.go):

```go
// UserSaver is the one method Registrar needs from storage. It is defined
// here, where it is used, not beside the storage implementation, so the
// storage package does not need to know about it and tests can fake it with
// one method.
type UserSaver interface {
	SaveUser(ctx context.Context, u User) error
}

// Mailer sends email.
type Mailer interface {
	Send(ctx context.Context, to, subject, body string) error
}
```

From [`examples/interfaces/users.go`](../examples/interfaces/users.go):

```go
// Registrar registers users. It accepts interfaces and is returned as a
// concrete type, so callers see every method it has.
type Registrar struct {
	users  UserSaver
	mailer Mailer
}

// NewRegistrar returns a Registrar that saves to users and sends with mailer.
func NewRegistrar(users UserSaver, mailer Mailer) *Registrar {
	return &Registrar{users: users, mailer: mailer}
}

// Register saves a user with the given ID and email and sends a welcome
// message.
func (r *Registrar) Register(ctx context.Context, id, email string) error {
	if err := r.users.SaveUser(ctx, User{ID: id, Email: email}); err != nil {
		return fmt.Errorf("register user %s: %w", id, err)
	}
	if err := r.mailer.Send(ctx, email, "Welcome", "Thanks for registering."); err != nil {
		return fmt.Errorf("register user %s: send welcome: %w", id, err)
	}
	return nil
}
```

The errors are wrapped with the user ID and the step that failed, so `register user u3: send welcome: smtp down` says where it broke.

A repository interface with ten methods forces each implementation, and each fake, to provide all ten. Split it by what callers use, and compose when a caller needs several:

From [`examples/interfaces/store.go`](../examples/interfaces/store.go):

```go
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
```

## Implement io.Reader and io.Writer

Many standard library functions take an `io.Reader` or `io.Writer`, so a type that implements one works with all of them. Check the standard ones first:

- `io.MultiReader` reads several readers one after another.
- `io.TeeReader` copies what it reads to a writer.
- `io.LimitReader` stops after n bytes.
- `io.MultiWriter` writes to several writers.

From [`examples/interfaces/io.go`](../examples/interfaces/io.go):

```go
// UpperReader upper-cases the ASCII letters it reads from R. Other bytes,
// including UTF-8 sequences, pass through unchanged.
type UpperReader struct {
	R io.Reader
}
```

Follow the `io.Reader` contract:

- Process only `p[:n]`, the bytes actually read.
- Return `n` and the error together, unchanged. A reader may return data and `io.EOF` in the same call. Callers handle the `n > 0` bytes before they look at the error.
- Avoid returning `0, nil` unless `len(p)` is 0. Callers read it as "nothing happened" and call again.

From [`examples/interfaces/io.go`](../examples/interfaces/io.go):

```go
// CountingWriter counts the bytes written through it to W.
type CountingWriter struct {
	W io.Writer
	N int64
}
```

From [`examples/interfaces/io.go`](../examples/interfaces/io.go):

```go
// Compile-time checks: the build fails if either type stops satisfying the
// interface, instead of a caller far away failing to compile.
var (
	_ io.Reader = (*UpperReader)(nil)
	_ io.Writer = (*CountingWriter)(nil)
)
```

## Check optional methods with a type assertion

A function that takes an `io.Writer` can check whether the writer also does more. `WriteAndFlush` flushes writers that buffer, such as `*bufio.Writer`, and leaves others alone. A buffered writer often reports a failure only when it flushes, so the flush error is returned too.

From [`examples/interfaces/io.go`](../examples/interfaces/io.go):

```go
// Flusher is implemented by writers that buffer, such as *bufio.Writer.
type Flusher interface {
	Flush() error
}
```

From [`examples/interfaces/io.go`](../examples/interfaces/io.go):

```go
// WriteAndFlush writes data to w and, if w also buffers, flushes it.
func WriteAndFlush(w io.Writer, data []byte) error {
	if _, err := w.Write(data); err != nil {
		return fmt.Errorf("write: %w", err)
	}
	if f, ok := w.(Flusher); ok {
		if err := f.Flush(); err != nil {
			return fmt.Errorf("flush: %w", err)
		}
	}
	return nil
}
```

## Embedding

Embedding a type in a struct promotes its methods: `Importer` gets a `Log` method from the `Logger` it embeds. Embedding is composition, not inheritance. The embedded value does not know about the outer struct.

From [`examples/interfaces/embedding.go`](../examples/interfaces/embedding.go):

```go
// discard is a Logger that drops every message.
type discard struct{}

func (discard) Log(string) {}

// Importer embeds a Logger, so its Log method is promoted: imp.Log(...)
// calls the embedded logger.
type Importer struct {
	Logger
}

// NewImporter returns an Importer that logs to logger, or discards messages
// when logger is nil, so the embedded interface is never nil.
func NewImporter(logger Logger) *Importer {
	if logger == nil {
		logger = discard{}
	}
	return &Importer{Logger: logger}
}
```

The constructor fills in a no-op logger for `nil`. A nil embedded interface compiles, then panics on the first `Log` call.

Embed only what you mean to expose. Embedding `sync.Mutex` in an exported struct adds `Lock` and `Unlock` to its API. Use a named field, `mu sync.Mutex`, instead. A struct with a mutex field must not be copied after first use. Pass it by pointer; `go vet` reports copies.

## Functional options

Functional options keep a constructor's signature stable as settings are added, and let callers set only what they need. Use them when a type has several optional settings with sensible defaults. For one or two settings, plain parameters or a config struct are simpler.

From [`examples/interfaces/options.go`](../examples/interfaces/options.go):

```go
// Option configures a Server.
type Option func(*Server)

// WithAddr sets the address the server listens on.
func WithAddr(addr string) Option {
	return func(s *Server) { s.addr = addr }
}

// WithTimeout sets the per-request timeout.
func WithTimeout(d time.Duration) Option {
	return func(s *Server) { s.timeout = d }
}

// WithMaxConns sets the maximum number of open connections. The parameter is
// n, not max, so it does not shadow the built-in max function.
func WithMaxConns(n int) Option {
	return func(s *Server) { s.maxConns = n }
}

// NewServer returns a Server with defaults, changed by any options given.
func NewServer(opts ...Option) *Server {
	s := &Server{
		addr:     "localhost:8080",
		timeout:  30 * time.Second,
		maxConns: 100,
	}
	for _, opt := range opts {
		opt(s)
	}
	return s
}
```

Name parameters so they do not shadow built-in functions: `WithMaxConns(n int)`, not `WithMaxConns(max int)`. Since Go 1.21, `min` and `max` are built-in functions.

## Type switches

A type switch binds the value to its concrete type in each case. Cases are checked in order, so put specific types before interfaces such as `fmt.Stringer`. A `case nil` matches a nil interface value.

From [`examples/interfaces/describe.go`](../examples/interfaces/describe.go):

```go
// Describe formats a value from a decoded JSON document. The type switch
// binds v to the concrete type in each case.
func Describe(value any) string {
	switch v := value.(type) {
	case nil:
		return "null"
	case string:
		return strconv.Quote(v)
	case float64:
		return strconv.FormatFloat(v, 'g', -1, 64)
	case bool:
		return strconv.FormatBool(v)
	case fmt.Stringer:
		return v.String()
	default:
		return fmt.Sprintf("%T", v)
	}
}
```

An interface holding a nil pointer is not nil, so `case nil` does not match it. The same trap applies to errors: see "Return a nil error as a literal nil" in `error-handling.md`.

## Pointer and value receivers

- Use a pointer receiver when the method changes the receiver or the struct is large. Use one too when the struct has a mutex or another field that must not be copied. Use a value receiver for small, immutable types such as `time.Time`.
- Do not mix the two on one type without a reason. Pick one and use it for every method.
- The method set of `T` contains only value-receiver methods. The method set of `*T` contains both. `Write` has a pointer receiver, so `*CountingWriter` is an `io.Writer`. `CountingWriter` is not. That is why the compile-time checks above use `(*T)(nil)`.

## Quick reference

| Practice | Why |
| --- | --- |
| Define interfaces where they are used | The implementation does not need to know its callers, and fakes stay small |
| Small interfaces, composed | Fewer methods to implement and fake |
| Accept interfaces, return `*T` | Callers get every method; the type can grow without breaking them |
| `-er` names for one-method interfaces | Matches the standard library: `Reader`, `Closer` |
| `v, ok := x.(T)` | A failed assertion is handled, not a panic |
| `var _ I = (*T)(nil)` | The build fails where the type is defined, not in a distant caller |
| Wrap errors in implementations | The caller learns which step failed |
