---
name: rust-sdk-dx
description: Applies CipherStash conventions for public Rust APIs in libraries, SDKs, and shared crates — thiserror error enums, typestate builders, required derives, newtype identifiers, ergonomic signatures, rustdoc sections, tokio async, crate layout, and feature flags. Use when writing or changing Rust library code that other developers consume, such as a crate with lib.rs, a public type or function, an error type, a builder, or module structure. Does not apply to application binaries, internal scripts, or non-Rust files, and defers secret handling to rust-security.
user-invocable: false
---

# Rust SDK Developer Experience

When writing Rust code that other developers will consume (libraries, SDKs, shared crates), follow these
conventions to produce ergonomic, idiomatic, and safe APIs.

## Error Handling

Use `thiserror` for all library error types. Never use `anyhow` or `Box<dyn Error>` in public APIs.

```rust
// GOOD
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum ClientError {
    #[error("authentication failed: {reason}")]
    AuthFailed { reason: String },

    #[error("request timed out after {duration:?}")]
    Timeout { duration: std::time::Duration },

    #[error(transparent)]
    Http(#[from] reqwest::Error),
}

// BAD - opaque, unmatchable, no context
pub type Error = Box<dyn std::error::Error + Send + Sync>;
```

Rules:
- Always `#[non_exhaustive]` on public error enums — allows adding variants without breaking downstream
- Error messages should be lowercase, no trailing punctuation, and describe what happened
- Include context in error variants (not just "failed", but *why*)
- Use `#[from]` for transparent wrapping of upstream errors
- Keep error types `Send + Sync + 'static` so callers can box and propagate them (true whenever every wrapped error is)
- Never panic in library code — no `unwrap()`, no `expect()`, no `panic!()`. Return `Result` instead

## Builder Pattern

Use builders for any struct with more than 2 configuration fields. Prefer the **typestate builder**
pattern for compile-time enforcement of required fields.

```rust
// Typestate builder — required fields enforced at compile time
pub struct ClientBuilder<AuthState = ()> {
    endpoint: Url,
    timeout: Option<Duration>,
    auth: AuthState,
}

impl ClientBuilder<()> {
    pub fn new(endpoint: impl Into<Url>) -> Self {
        Self {
            endpoint: endpoint.into(),
            timeout: None,
            auth: (),
        }
    }

    /// Set the authentication credentials. Required before calling `build()`.
    pub fn with_auth(self, credentials: Credentials) -> ClientBuilder<Credentials> {
        ClientBuilder {
            endpoint: self.endpoint,
            timeout: self.timeout,
            auth: credentials,
        }
    }
}

impl ClientBuilder<Credentials> {
    pub fn build(self) -> Result<Client, ClientError> {
        // only available when auth is provided
    }
}

// Optional fields use regular methods returning Self
impl<A> ClientBuilder<A> {
    pub fn timeout(mut self, duration: Duration) -> Self {
        self.timeout = Some(duration);
        self
    }
}
```

Rules:
- `build()` returns `Result<T, BuilderError>`, never panics
- Optional fields have sensible defaults and use `Option<T>` internally
- Provide a `::new()` with only truly mandatory params, or a `::builder()` associated fn on the target type
- Accept `impl Into<T>` on builder methods for ergonomic string/URL/etc. inputs

For simpler cases (all fields optional or 2-3 fields), a basic builder is fine:

```rust
impl Config {
    pub fn builder() -> ConfigBuilder {
        ConfigBuilder::default()
    }
}
```

## Public API Surface

### Derives and Traits

Every public type must derive or implement:
- `Debug` — always (types containing secrets use a redacted `Debug`, as rust-security specifies)
- `Clone` — unless the type manages a unique resource (connection, file handle) or holds a secret (rust-security decides when a secret type may be `Clone`)
- `Send + Sync` — for all types that may cross thread boundaries (most library types)

Apply where appropriate:
- `PartialEq, Eq` — for value types, IDs, enums
- `Hash` — if the type may be used as a map key
- `Default` — when there's an obvious default state
- `serde::Serialize, serde::Deserialize` — behind a `serde` feature flag

```rust
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct AccountId(Uuid);
```

### Type Design

- **Newtype wrappers** for domain identifiers — `AccountId(Uuid)` not raw `Uuid`
- **`#[non_exhaustive]`** on all public enums and structs with public fields
- **`#[must_use]`** on functions returning `Result` or types where ignoring the return value is a bug
- **Sealed traits** for traits that define an extension point but shouldn't be implemented downstream

```rust
// Newtype with conversions
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub struct AccountId(Uuid);

impl From<Uuid> for AccountId {
    fn from(id: Uuid) -> Self {
        Self(id)
    }
}

impl fmt::Display for AccountId {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        self.0.fmt(f)
    }
}
```

### Function Signatures

- Accept generous input types: `impl Into<String>`, `impl AsRef<Path>`, `impl AsRef<[u8]>`
- Return concrete types, not `impl Trait` (unless there's a strong reason — it prevents naming the type)
- Use `&self` over `&mut self` where possible — prefer interior mutability if mutation is needed
- Avoid `&String`, `&Vec<T>` — use `&str`, `&[T]` instead

```rust
// GOOD — caller can pass &str, String, Cow<str>, etc.
pub fn set_name(&mut self, name: impl Into<String>) {
    self.name = name.into();
}

// BAD — forces caller to allocate a String
pub fn set_name(&mut self, name: String) { ... }
```

## Documentation

Every public item (`pub fn`, `pub struct`, `pub enum`, `pub trait`, `pub mod`) must have a doc comment.

```rust
/// A fixed-size buffer that wraps around when full.
///
/// # Examples
///
/// ```
/// use my_crate::RingBuffer;
///
/// let mut buf = RingBuffer::new(3);
/// buf.push(1);
/// buf.push(2);
/// buf.push(3);
/// buf.push(4); // overwrites the oldest element
///
/// assert_eq!(buf.len(), 3);
/// assert_eq!(buf.oldest(), Some(&2));
/// ```
pub struct RingBuffer<T> { ... }
```

Rules:
- First line is a concise summary (shows up in rustdoc index)
- Include a `# Examples` section with a compilable code block for key types and functions
- Use `# Errors` section on functions that return `Result` to document when each error variant occurs
- Use `# Panics` section if the function can panic (it shouldn't in library code, but document if unavoidable)
- Module-level docs (`//!`) should explain the *concept*, not just list the types

## Async Conventions

Use `tokio` as the async runtime. Do not try to be runtime-agnostic unless the crate specifically needs it.

Rules:
- Async functions should be async all the way — don't mix `block_on` with async
- Use `tokio::sync` primitives (`Mutex`, `RwLock`, `Semaphore`) not `std::sync` in async code
- Accept `impl Into<T>` rather than making every input function async
- Timeouts should be configurable, not hardcoded
- Use `reqwest` for HTTP clients — it integrates well with tokio

## Crate Structure

### lib.rs Organization

Re-export the primary public types at the crate root. Users should be able to use the most common
types with a single `use my_crate::Thing` import.

```rust
//! Client library for the FooBar service.
//!
//! # Quick start
//!
//! ```rust
//! let client = my_crate::Client::builder()
//!     .with_auth(credentials)
//!     .build()?;
//! ```

mod client;
mod config;
mod error;
mod types;

pub use client::Client;
pub use config::Config;
pub use error::ClientError;
pub use types::{AccountId, ProjectId};

// Re-export sub-modules for less common types
pub mod models;
pub mod auth;
```

### Feature Flags

- `default = []` — keep defaults minimal
- Gate optional dependencies behind features: `serde`, `tracing`, `test-utils`
- Re-export dependency types that appear in your public API signatures
- Use `#[cfg(feature = "...")]` on modules and re-exports, not scattered through code

```toml
[features]
default = []
serde = ["dep:serde", "uuid/serde"]
tracing = ["dep:tracing"]
test-utils = ["dep:fake", "dep:rand"]
```

## Security-Sensitive Types

For types that hold secrets (tokens, keys, passwords), follow the `rust-security` skill in this plugin: it sets the company rules for redacted `Debug`, zeroization, constant-time comparison, and when `Clone` is allowed. Never put a secret in `Display` output or an error message.

## Anti-Patterns to Avoid

- **Stringly-typed APIs** — use enums or newtypes, not `&str` for fixed sets of values
- **Leaking internal types** — don't expose internal module paths in public signatures
- **`Box<dyn Error>`** as a public error type — use a concrete enum
- **`pub use crate::internal::*`** — be explicit about what you re-export
- **Over-generic signatures** — `where T: AsRef<str> + Into<String> + Clone + Send + 'static`
  is worse than just `String` unless you genuinely need the flexibility
- **Boolean parameters** — use a two-variant enum instead for clarity at call sites
- **Returning `()`** when a meaningful result could be returned (e.g. the created resource)
