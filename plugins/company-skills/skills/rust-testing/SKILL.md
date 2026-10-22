---
name: rust-testing
description: Applies CipherStash conventions for Rust tests — running unit and integration tests with nextest and its test groups, nested given_* scenario modules with expectation-style names, assertion messages, randomised test data with fake and Dummy impls behind a test-utils feature, per-test mocktail HTTP mocks, paused-time tokio tests, concurrency stress tests, and testing napi-rs boundaries. Use when writing or changing Rust tests (#[test], #[tokio::test]), test modules, test fixtures or helpers, mock servers, or test configuration such as .config/nextest.toml. Does not apply to production Rust code with no test changes, documentation, or tests in other languages, except JavaScript tests that exercise a napi-rs crate's test-utils mocks.
user-invocable: false
---

# Rust Testing Conventions

Follow these conventions when writing or modifying Rust tests.

API examples target `mocktail` 0.3, `fake` 2.10–3.x with `rand` 0.8, `axum` 0.8, and `tokio` 1.x. On other versions the names may differ; check the crate's docs before copying.

## Test Runner & Configuration

Use `nextest` for all unit and integration tests. Use `cargo test` only for doc tests, which nextest does not run.

### Running tests

1. Use the repository's own test tasks when it defines them — a mise task, a Makefile or justfile target, or a cargo alias in `.cargo/config.toml`. For example, a repository using mise may define `mise run test:unit` and `mise run test:doc`.
2. Load the repository's test environment the way it documents (for example `mise x --env test -- <command>`, a `.env.test` file, or a `docker compose` service for the database). Do not guess environment variables.
3. When the repository defines no task, fall back to plain commands:

```bash
# Specific package/test
cargo nextest run -p <package> -- <test_pattern>

# Doc tests (nextest doesn't support these)
cargo test --doc -p <package>
```

### Test groups

Configure test groups in `.config/nextest.toml`. Use them to control concurrency for resource-heavy tests:

```toml
[test-groups]
resource-limited = { max-threads = 2 }
serial-integration = { max-threads = 1 }

[[profile.ci.overrides]]
filter = 'package(<heavy-package>)'
test-group = 'resource-limited'
```

Under nextest, never use `serial_test` — it doesn't coordinate across nextest's per-test processes; use a test group (`max-threads = 1`) instead, or better, randomise data so tests can run concurrently. Repos that still run under `cargo test` may use `serial_test` until they move to nextest.

## Test Organisation & Naming

### Nested modules for scenarios

Structure tests as nested modules representing scenarios. The module name is the context; the function name is the assertion:

```rust
#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::*;

    mod given_existing_workspace {
        use super::*;

        async fn scenario() -> (Scenario<HandlerTestCase>, WorkspaceId) {
            let scenario = super::scenario().await.unwrap();
            let workspace_id = create_workspace(&scenario).await.unwrap();
            (scenario, workspace_id)
        }

        #[tokio::test]
        async fn returns_success() {
            let (scenario, workspace_id) = scenario().await;
            let response = scenario.do_the_test(workspace_id).await.unwrap();
            assertions::response_is_ok(&response);
        }
    }
}
```

### Expectation-style naming

Tests read as assertions. The module gives the context, the function gives the expectation:

```rust
// GOOD — reads as "given empty workspace → returns error"
mod tests {
    mod given_empty_workspace {
        #[test]
        fn returns_error() { ... }
    }
}

// BAD — long name trying to encode both context and expectation
#[test]
fn test_returns_error_given_valid_workspace_with_no_membership() { ... }
```

### Reusable assertions

Extract repeated assertions into an `assertions` submodule:

```rust
mod tests {
    #[test]
    fn it_works() {
        assertions::response_is_ok(&response);
    }

    pub(crate) mod assertions {
        pub(crate) fn response_is_ok(response: &Response) {
            assert_eq!(response.status(), 200, "response should be 200 OK");
        }
    }
}
```

### Assertion messages

Always include a descriptive message as the final argument to `assert!`, `assert_eq!`, and `assert_ne!`. This makes failures self-explanatory without needing to re-read the test:

```rust
// GOOD — failure message tells you what went wrong
assert_eq!(token.as_str(), "new-token", "cached token should be returned");
assert!(token.is_valid(), "token should still be valid after refresh");
assert!(
    matches!(err, AuthError::InvalidClient),
    "expected InvalidClient, got: {err:?}"
);

// BAD — failure just shows values with no context
assert_eq!(token.as_str(), "new-token");
assert!(token.is_valid());
```

Include the actual value in `assert!` messages using `{variable:?}` so the failure output shows what was received.

### Separate test files

For large test suites, extract tests into a dedicated file:

```rust
// src/device_code.rs
#[cfg(test)]
mod tests;

// src/device_code/tests.rs
use super::*;
// ... tests here
```

## Randomise Data to Avoid Database Locks

Always use generated IDs instead of hardcoded values. Hardcoded IDs cause `ROW EXCLUSIVE` lock contention in Postgres, making parallel tests slow or flaky:

```rust
// GOOD — each test gets a unique workspace
let workspace_id = WorkspaceId::generate()?;

// BAD — all tests fight over the same row
let workspace_id = WorkspaceId::try_from("3J7ZGPGELUZXHDKD")?;
```

## Generating Test Data with `fake`

Use the `fake` crate to generate realistic random test data. This is especially useful for domain types that appear frequently in tests.

### Inline generation

Use `Faker.fake()` with type inference for simple cases:

```rust
use fake::{Fake, Faker};

let key: String = Faker.fake();
let region: Region = Faker.fake();
```

### `Dummy` trait implementations

Implement `fake::Dummy` on domain types to make them easy to generate. Use different generic parameters to support multiple test scenarios:

```rust
#[cfg(feature = "test-utils")]
impl fake::Dummy<()> for User {
    fn dummy_with_rng<R: rand::Rng + ?Sized>(_: &(), rng: &mut R) -> Self {
        use fake::Fake;
        let external_id: String = fake::Faker.fake();
        Self {
            id: create_user_id_from_external(&external_id),
            external_id,
            role: None,
            workspace_id: None,
            // ...
        }
    }
}

// Variant that accepts a Role parameter
#[cfg(feature = "test-utils")]
impl fake::Dummy<Role> for User {
    fn dummy_with_rng<R: rand::Rng + ?Sized>(role: &Role, rng: &mut R) -> Self {
        // ... generate user with the given role
    }
}
```

### Custom marker structs

For generating specific data shapes (e.g. hostnames, URLs), define a marker struct:

```rust
pub struct Hostname;

impl fake::Dummy<Hostname> for String {
    fn dummy_with_rng<R: rand::Rng + ?Sized>(_: &Hostname, rng: &mut R) -> Self {
        generate_random_hostname(rng)
    }
}
```

### Feature-gating

Gate `Dummy` implementations behind a `test-utils` feature so they don't ship in production:

```toml
[features]
test-utils = ["dep:fake"]

[dependencies]
fake = { workspace = true, optional = true }  # `dep:` needs an optional regular dependency

[dev-dependencies]
fake = { workspace = true }
```

## Unit Testing HTTP Clients with `mocktail`

Use `mocktail` as the standard HTTP mocking library. Each test creates its own `MockServer` — no shared state between tests.

### Basic pattern

```rust
use mocktail::prelude::*;

// Response builders — keep at the top of the test module
fn device_code_json() -> serde_json::Value {
    serde_json::json!({
        "device_code": "test_device_code",
        "user_code": "ABCD-EFGH",
        "verification_uri": "http://example.com/activate",
        "verification_uri_complete": "http://example.com/activate?user_code=ABCD-EFGH",
        "expires_in": 900
    })
}

fn error_json(error: &str) -> serde_json::Value {
    serde_json::json!({
        "error": error,
        "error_description": format!("{error} occurred")
    })
}

// Mock registration helper
fn mock_code_endpoint(mocks: &mut MockSet) {
    mocks.mock(|when, then| {
        when.post().path("/oauth/device/code");
        then.json(device_code_json());
    });
}

// Server setup helper
async fn start_server(mocks: MockSet) -> MockServer {
    let server = MockServer::new_http("my-test").with_mocks(mocks);
    server.start().await.unwrap();
    server
}

// Strategy/client factory — injects the mock URL
fn strategy_for(server: &MockServer) -> MyClient {
    MyClient::builder()
        .base_url(server.url(""))
        .build()
        .unwrap()
}
```

### Success and error tests

```rust
mod begin {
    use super::*;

    #[tokio::test]
    async fn returns_pending_device_code() {
        let mut mocks = MockSet::new();
        mock_code_endpoint(&mut mocks);
        let server = start_server(mocks).await;

        let pending = strategy_for(&server).begin().await.unwrap();

        assert_eq!(pending.user_code(), "ABCD-EFGH", "user code should match");
    }

    mod given_invalid_client {
        use super::*;

        #[tokio::test]
        async fn returns_invalid_client_error() {
            let mut mocks = MockSet::new();
            mocks.mock(|when, then| {
                when.post().path("/oauth/device/code");
                then.bad_request().json(error_json("invalid_client"));
            });
            let server = start_server(mocks).await;

            let err = strategy_for(&server).begin().await.unwrap_err();

            assert!(
                matches!(err, AuthError::InvalidClient),
                "expected InvalidClient, got: {err:?}"
            );
        }
    }
}
```

### Error response helpers

The fluent API provides status code helpers:

```rust
then.bad_request().json(error_json("invalid_client"));      // 400
then.unauthorized().json(error_json("invalid key"));         // 401
then.internal_server_error().json(error_json("boom"));       // 500
```

### Dynamic mock swapping

Swap mocks mid-test to simulate state changes (e.g. polling, caching, retry):

```rust
#[tokio::test]
async fn test_caches_token_after_initial_auth() {
    let mut mocks = MockSet::new();
    mocks.mock(|when, then| {
        when.post().path("/api/authorise");
        then.json(auth_response_json("new-token", 3600));
    });
    let server = start_server(mocks).await;
    let strategy = make_strategy(&server);

    let token1 = strategy.get_token().await.unwrap();
    assert_eq!(token1.as_str(), "new-token", "initial auth should return new token");

    // Swap mock — second call should use cached token, not hit server
    server.mocks().clear();
    server.mocks().mock(|when, then| {
        when.post().path("/api/authorise");
        then.internal_server_error()
            .json(serde_json::json!({"error": "should not be called"}));
    });

    let token2 = strategy.get_token().await.unwrap();
    assert_eq!(token2.as_str(), "new-token", "cached token should be returned");
}
```

For concurrent mock swapping (e.g. polling loops), use `tokio::join!`:

```rust
#[tokio::test(start_paused = true)]
async fn test_poll_pending_then_success() {
    let mut mocks = MockSet::new();
    mock_code_endpoint(&mut mocks);
    mocks.mock(|when, then| {
        when.post().path("/oauth/device/token");
        then.bad_request().json(error_json("authorization_pending"));
    });
    let server = start_server(mocks).await;
    let pending = begin_pending(&server).await;

    let (result, _) = tokio::join!(pending.poll_for_token(), async {
        tokio::time::sleep(tokio::time::Duration::from_secs(6)).await;
        server.mocks().clear();
        server.mocks().mock(|when, then| {
            when.post().path("/oauth/device/token");
            then.json(token_json());
        });
    });

    let token = result.unwrap();
    assert_eq!(token.access_token().0, "test_access_token_value", "should receive token after mock swap");
}
```

## Time-Controlled Async Tests

Use `start_paused = true` for any test that involves timers, polling, or sleep logic:

```rust
#[tokio::test(start_paused = true)]
async fn test_poll_for_token_success() {
    // Timer operations (tokio::time::sleep) advance the clock instantly.
    // I/O (HTTP requests to mock server) still works normally.
    // Without this, a test with 5s poll intervals takes 5+ real seconds.
}
```

Use this whenever the code under test calls `tokio::time::sleep`, `tokio::time::interval`, or any timer-based logic.

## Concurrency & Stress Tests

Put tests that verify concurrency properties (single-flight requests, peak in-flight counts, lock contention) in a separate `stress_tests` module, run them on a `multi_thread` runtime, count requests with a `CountingState`, and simulate latency with a real Axum server rather than mocktail. Read [references/stress-testing.md](references/stress-testing.md) when writing or changing a concurrency or stress test.

## Testing napi-rs Boundaries

Test the Rust side of FFI functions directly in `#[cfg(test)]`, check every error variant's code mapping and the `"CODE: message"` error format, check that one-shot handles cannot be reused, and expose mock servers to JavaScript tests through the `test-utils` feature. Read [references/napi-testing.md](references/napi-testing.md) when the crate exposes Rust to JavaScript through napi-rs.

## Test Helpers & Fixtures

Keep test helpers close to the tests that use them:

- **Response builders**: `fn device_code_json() -> serde_json::Value` — returns canned JSON
- **Server setup**: `async fn start_server(mocks: MockSet) -> MockServer` — creates and starts a mock server
- **Client factory**: `fn strategy_for(server: &MockServer) -> T` — injects mock URL into the client
- **Shared helpers**: put in the same test module or a `test_support` module if used across files

## Rules Summary

1. Always use `nextest` (except doc tests)
2. Run tests through the repository's own test tasks and test environment when it defines them; otherwise `cargo nextest run -p <package> -- <pattern>`
3. Use nextest test groups, not `serial_test`, to limit concurrency under nextest
4. Randomize data to avoid DB lock contention — use `fake` crate and `Dummy` implementations for domain types
5. Prefer `mocktail` for HTTP mocking; keep a crate's existing mocking library when it already uses another
6. Use `start_paused = true` for any test with timer/sleep logic
7. Each test gets its own mock server — no shared state
8. Test error paths as thoroughly as success paths
9. Use `#[allow(clippy::unwrap_used)]` on test modules (`.unwrap()` is fine in tests)
10. Name tests with expectation style: `mod given_<scenario> { fn returns_<expectation>() }`
11. Always include a descriptive message in `assert!`, `assert_eq!`, and `assert_ne!` calls
