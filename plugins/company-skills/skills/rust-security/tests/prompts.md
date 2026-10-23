# Behavior cases

This is a background convention skill: it is applied while the agent writes code, not invoked by name.

## Should activate

- "Add an `ApiKey` type to this crate that we can compare against the stored value and encrypt before writing it to Postgres." (in a Rust crate that depends on vitaminc)
- "We keep seeing session tokens in our logs; fix it." (in a Rust service whose token type derives `Debug`)
- "Generate a verification code for the sign-in flow" in a Rust crate with no other detail — the agent asks or checks which code format, length, and storage are needed, rather than guessing.

## Should not activate

- "Add pagination to the `list_users` endpoint" in a Rust service, where no secret, key, or credential is touched.
- "Hash this password in our TypeScript signup handler."
- "Give this SDK's `Client` a typestate builder and a proper error enum" — public API shape is rust-sdk-dx's job, unless the client holds credentials, where both apply.

## Expected behavior

- Crates that handle secrets carry the crate-level security lint block at the top of `lib.rs`, with test-only relaxations under `cfg_attr(test, ...)`.
- Secret values live in a newtype over vitaminc's `Protected<T>` with a redacted `Debug`; the type does not derive `Debug` or, without a documented need, `Clone`, and never implements `AsRef` or `Deref` over the raw value.
- Secret comparisons are constant-time through vitaminc's `Equatable`, never `==`; secret values are never used as indices.
- Every vitaminc call is checked against the vitaminc skill or docs.rs for the version in `Cargo.toml`, not written from memory; the agent does not use APIs such as `timing_safe_eq`, `encrypt_with_aad`, or an infallible `SafeRand::from_entropy()`.
- Encryption goes through vitaminc's AEAD with a context that names where the ciphertext lives; a value used for storage and for clients gets per-purpose types so the two ciphertexts cannot open under each other.
- Blind indexes use vitaminc's PRF with a context; structured data outside vitaminc is hashed with `udigest`, not by concatenating fields.
- Crypto failures surface as one opaque error; HTTP boundaries return generic 401/403/500; details go to `tracing` via `inspect_err`.
- Access decisions use only verified JWTs.
- Randomness for secrets comes from vitaminc, never `thread_rng()`.
- Secret bytes vitaminc does not own are encoded with `serdect`, `base16ct`, or `base64ct`, and intermediate buffers are zeroized.
- Functions taking secrets use `#[instrument(skip_all)]` or `skip(...)`, and no secret reaches a log line, `Display`, or an error message.
- The agent does not invent vitaminc APIs, crate names, or domain types that are not in the vitaminc docs or the user's codebase.
