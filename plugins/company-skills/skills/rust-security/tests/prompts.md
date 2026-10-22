# Behavior cases

This is a background convention skill: it is applied while the agent writes code, not invoked by name.

## Should activate

- "Add an `ApiKey` type to this crate that we can compare against the stored value and encrypt before writing it to Postgres." (in a Rust crate that depends on vitaminc)
- "We keep seeing session tokens in our logs; fix it." (in a Rust service whose token type derives `Debug`)
- "Generate a verification code for the sign-in flow" in a Rust crate with no other detail — the agent asks or checks which code format, length, and storage are needed, and which vitaminc version the crate uses, rather than guessing.

## Should not activate

- "Add pagination to the `list_users` endpoint" in a Rust service, where no secret, key, or credential is touched.
- "Hash this password in our TypeScript signup handler."
- "Give this SDK's `Client` a typestate builder and a proper error enum" — public API shape is rust-sdk-dx's job, unless the client holds credentials, where both apply.

## Expected behavior

- Crates that handle secrets carry the crate-level security lint block at the top of `lib.rs`, with test-only relaxations under `cfg_attr(test, ...)`.
- Secret types derive `OpaqueDebug`, `ZeroizeOnDrop`, and `TimingSafeEq`; they do not derive `Debug` or, without a documented need, `Clone`, and they never implement `AsRef` or `Deref` over the raw value.
- Secret comparisons use `timing_safe_eq`, never `==`; secret values are never used as indices.
- Encryption goes through vitaminc `Encrypt` / `Decrypt` (derived where possible) with AAD that binds the purpose and, where relevant, the tenant or scope; a value used for storage and for clients gets per-purpose types so the two ciphertexts cannot open under each other.
- Derived keys use blake3 with a fixed domain string, and hasher state is zeroized; structured data is hashed with `udigest`, not by concatenating fields.
- Crypto failures surface as one opaque `Unspecified` error; HTTP boundaries return generic 401/403/500; details go to `tracing` via `inspect_err`.
- Access decisions use only verified JWTs.
- Randomness comes from `SafeRand::from_entropy()` and `next_below`, never `thread_rng()`.
- Secret bytes are encoded with `serdect`, `base16ct`, or `base64ct`, and intermediate buffers are zeroized.
- Functions taking secrets use `#[instrument(skip_all)]` or `skip(...)`, and no secret reaches a log line, `Display`, or an error message.
- If the crate pins a pre-0.5 vitaminc (for example `0.1.0-pre`), the agent says the examples need vitaminc 0.5 and proposes the upgrade instead of writing code that will not compile.
- The agent does not invent vitaminc APIs, crate names, or domain types that are not in the skill or the user's codebase.
