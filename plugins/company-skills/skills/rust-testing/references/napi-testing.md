# Unit Testing FFI / NAPI Boundaries

## Contents

- [Test Rust functions directly](#test-rust-functions-directly)
- [Test error mapping](#test-error-mapping)
- [Test NAPI error format](#test-napi-error-format)
- [Test consumed handle semantics](#test-consumed-handle-semantics)
- [`test-utils` cargo feature](#test-utils-cargo-feature)
- [JS-side integration tests (vitest)](#js-side-integration-tests-vitest)

Read this when the crate exposes Rust to JavaScript through napi-rs. The naming, assertion-message, mocktail, and paused-time conventions in the main skill apply here too. `error_code`, `to_napi_error`, and `MockAuthServer` below are examples of the pattern, not existing APIs; use the crate's own names.

## Test Rust functions directly

Test the Rust FFI functions in `#[cfg(test)]` — no need to load the native module:

```rust
#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::*;
    use mocktail::prelude::*;

    // Same mocktail pattern as pure-Rust client tests
    async fn start_server(mocks: MockSet) -> MockServer {
        let server = MockServer::new_http("my-napi-test").with_mocks(mocks);
        server.start().await.unwrap();
        server
    }
}
```

## Test error mapping

Verify each error variant maps to the correct code string:

```rust
#[test]
fn test_error_code_mapping() {
    assert_eq!(error_code(&AuthError::AccessDenied), "ACCESS_DENIED", "AccessDenied should map to ACCESS_DENIED");
    assert_eq!(error_code(&AuthError::ExpiredToken), "EXPIRED_TOKEN", "ExpiredToken should map to EXPIRED_TOKEN");
    assert_eq!(error_code(&AuthError::InvalidGrant), "INVALID_GRANT", "InvalidGrant should map to INVALID_GRANT");
    assert_eq!(error_code(&AuthError::InvalidClient), "INVALID_CLIENT", "InvalidClient should map to INVALID_CLIENT");
}
```

## Test NAPI error format

Verify `to_napi_error()` produces the expected `"CODE: message"` format:

```rust
#[test]
fn test_napi_error_format() {
    let err = to_napi_error(AuthError::AccessDenied);
    assert!(
        err.reason.starts_with("ACCESS_DENIED: "),
        "expected 'ACCESS_DENIED: ...' but got: {}",
        err.reason
    );
}
```

## Test consumed handle semantics

Verify that one-shot handles cannot be reused:

```rust
#[tokio::test(start_paused = true)]
async fn test_poll_for_token_already_consumed() {
    // setup ...
    let result = begin_result(&server).await;
    result.poll_for_token().await.unwrap();  // first call consumes

    let err = result.poll_for_token().await.unwrap_err();  // second call fails
    assert!(
        err.reason.contains("already been consumed"),
        "second call should fail with consumed error, got: {}",
        err.reason
    );
}
```

## `test-utils` cargo feature

Expose test-only types to JavaScript via `#[cfg(feature = "test-utils")]`:

```rust
// Cargo.toml
[features]
test-utils = ["dep:mocktail"]

// mock_auth_server.rs
#[cfg(feature = "test-utils")]
mod mock_auth_server;

// The mock server is a #[napi] struct available to JS tests
#[napi]
pub struct MockAuthServer {
    server: MockServer,
}

#[napi]
impl MockAuthServer {
    #[napi(factory)]
    pub async fn start() -> Result<Self> { ... }

    #[napi]
    pub fn mock_device_code_endpoint(&self) { ... }

    #[napi]
    pub fn clear_mocks(&self) { ... }
}
```

## JS-side integration tests (vitest)

Load the CJS module and use `MockAuthServer` from the `test-utils` feature:

```typescript
const mod = require("../index.js") as typeof import("../index") & {
  MockAuthServer: typeof MockAuthServerType;
};

describe("device code flow", () => {
  let server: InstanceType<typeof MockAuthServerType>;

  beforeEach(async () => {
    server = await MockAuthServer.start();
    server.mockDeviceCodeEndpoint();
  });

  it("attaches .code for INVALID_REGION", async () => {
    try {
      await beginDeviceCodeFlow("not-a-region", "test-client");
      expect.unreachable("should have thrown");
    } catch (err) {
      const authErr = err as AuthError;
      expect(authErr).toBeInstanceOf(Error);
      expect(authErr.code).toBe("INVALID_REGION");
    }
  });
});
```
