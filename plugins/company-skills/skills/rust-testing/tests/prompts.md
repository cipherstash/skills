# Behavior cases

This is a background convention skill: it is applied while the agent writes code, not invoked by name.

## Should activate

- "Add tests for the token refresh path in `auth/client.rs`, including the 401 and 500 responses." (in a Rust crate)
- "These integration tests are flaky when they run in parallel against Postgres; fix them." (in a Rust workspace)
- "Add some tests for this" with a Rust module open and no other detail — the agent asks which behavior or scenarios to cover, or proposes a short list of `given_<scenario>` cases, rather than writing tests for everything.

## Should not activate

- "Add a retry with backoff to `get_token`" with no test changes requested.
- "Write Jest tests for this React component."
- "Add a public builder for the client config" — public API shape is rust-sdk-dx's job, though both apply if the change also adds tests.

## Expected behavior

- Tests run with `cargo nextest run`; `cargo test` is used only for doc tests. The agent uses the repository's own test tasks and test environment when it defines them (mise, make, just, cargo aliases), and falls back to `cargo nextest run -p <package> -- <pattern>` otherwise; it does not invent task names or environment variables.
- Tests sit in nested `given_<scenario>` modules with expectation-style function names such as `returns_error`; repeated checks live in an `assertions` submodule.
- Every `assert!`, `assert_eq!`, and `assert_ne!` carries a descriptive message, with the actual value via `{value:?}` in `assert!` messages.
- For flaky parallel database tests, the agent replaces hardcoded IDs with generated or `fake` data, or assigns the tests to a nextest test group; under nextest it does not add `serial_test`, though it leaves `serial_test` alone in a repository that still runs `cargo test`.
- `Dummy` impls and other test-only helpers are gated behind a `test-utils` feature.
- HTTP client tests start their own mocktail `MockServer` per test and cover error responses as well as success; tests with timers or polling use `#[tokio::test(start_paused = true)]`.
- For a napi-rs crate, the agent reads `references/napi-testing.md`; for a concurrency test, `references/stress-testing.md`.
- The agent does not invent crate helpers, error variants, or endpoints that are not in the user's codebase.
