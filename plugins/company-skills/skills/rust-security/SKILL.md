---
name: rust-security
description: Applies CipherStash company rules for Rust code that handles secrets, cryptography, and authentication — the crate-level security lint block, opaque secret types with no AsRef or Deref, crypto library order (vitaminc, then aws-lc-rs, then RustCrypto), one encryption context per purpose, udigest for structured hashes, opaque errors at crypto and HTTP boundaries, JWT verification, constant-time encoding, and logging discipline. Defers vitaminc types and APIs (Protected, Equatable, AEAD, PRF, SafeRand) to the vitaminc skill or docs.rs. Use when writing or changing Rust code that encrypts or decrypts, derives or stores keys, defines a token, key, password, or other secret type, compares or hashes secret values, generates security-relevant randomness, verifies credentials or JWTs, or serializes or logs data that may contain secrets. Does not apply to Rust code with no secret or crypto handling, non-Rust code, or general public API design, which rust-sdk-dx owns.
user-invocable: false
---

# Secure Rust Coding

When writing Rust code that handles secrets, cryptographic operations, or authentication, follow these company rules to prevent information leaks, side-channel attacks, and cryptographic misuse.

This skill holds the rules; it does not teach the vitaminc API.
Whenever code names a vitaminc type or function (`Protected`, `Equatable`, `OpaqueDebug`, `encrypt` / `decrypt` and the AEAD derives, `IntoContext`, `HmacSha256Prf`, `ProtectedDigest`, `SafeRand`, `Generatable`), use the vitaminc skill if it is loaded, otherwise the docs for the version in the crate's `Cargo.toml` at <https://docs.rs/vitaminc>.
Do not write vitaminc calls from memory: the API changes between releases.

For public library API design (error enums, builders, derives, docs), follow the rust-sdk-dx skill in this plugin.

## Crate-level security lints

Every crate that handles secrets, authentication, or cryptographic material must include this lint block at the top of `lib.rs`:

```rust
// Security lints
#![deny(unsafe_code)]
#![warn(clippy::unwrap_used)]
#![warn(clippy::expect_used)]
#![warn(clippy::panic)]
// Prevent mem::forget from bypassing ZeroizeOnDrop
#![warn(clippy::mem_forget)]
// Prevent accidental data leaks via output
#![warn(clippy::print_stdout)]
#![warn(clippy::print_stderr)]
#![warn(clippy::dbg_macro)]
// Code quality
#![warn(unreachable_pub)]
#![warn(unused_results)]
#![warn(clippy::todo)]
#![warn(clippy::unimplemented)]
// Relax in tests
#![cfg_attr(test, allow(clippy::unwrap_used))]
#![cfg_attr(test, allow(clippy::expect_used))]
#![cfg_attr(test, allow(clippy::panic))]
#![cfg_attr(test, allow(unused_results))]
```

- `deny(unsafe_code)`: no unsafe; use safe abstractions from vetted crates.
- `clippy::mem_forget`: `mem::forget` skips `Drop`, so zeroize-on-drop never runs.
- `clippy::print_stdout`, `print_stderr`, `dbg_macro`: stop secrets reaching the console.
- Test relaxations are `cfg_attr(test, ...)`, so production code keeps the full set.

## Secret types

Hold secret values in vitaminc's `Protected<T>` inside a domain newtype, for example `struct ApiKey(Protected<String>)`.
`Protected` zeroizes on drop and redacts `Debug`; derive `OpaqueDebug` on the newtype and compare with `Equatable`, never `==`.
See the vitaminc skill or docs.rs for the exact derives and comparison API.

Company rules on top of that:

- Never derive `Debug` on a type that holds a secret.
- Do not derive or implement `Clone` on a secret type without a documented need; every copy must also zeroize on drop.
- Do not derive `Serialize` / `Deserialize` on raw secret types; use the constant-time encoders under Serialization.
- Mark non-secret fields (IDs, metadata) so they are not zeroized, for example `#[zeroize(skip)]` when the type derives `Zeroize` directly.
- Never use secret values as array or map indices or branch on them; cache and branch timing reveal them.

## Opaque secret type design

Secret types are opaque wrappers that prefer consuming (move) semantics.

```rust
// GOOD — consuming self; internal-only access to the raw value
impl Verifier {
    pub fn encode(self) -> EncodedVerifier { /* ... */ }

    pub(crate) fn expose(&self) -> &[u8] { /* ... */ }
}

// BAD — AsRef hands callers the raw value, so they compare it with ==
impl AsRef<[u8]> for Verifier {
    fn as_ref(&self) -> &[u8] { /* ... */ }
}

// BAD — Deref exposes the inner value implicitly
impl Deref for Verifier {
    type Target = [u8];
    fn deref(&self) -> &[u8] { /* ... */ }
}
```

- Never implement `AsRef`, `Deref`, `Borrow`, or similar on a secret type: it bypasses constant-time comparison and lets the raw value escape.
- Prefer consuming `self` over `&self`, so the value moves instead of being copied.
- Public API accepts and returns the opaque wrapper; only internal code touches raw data, through `pub(crate)` methods, not public traits.

## Crypto library preference

1. **`vitaminc`** (built on `aws-lc-rs`): encryption, decryption, keyed hashing, and secret randomness.
2. **`aws-lc-rs`**: direct primitive needs vitaminc does not cover (FIPS-validated, hardware-accelerated).
3. **RustCrypto crates** (`sha2`, `hmac`, and so on): acceptable fallback.
4. **Never** implement primitives from scratch.

## Cryptographic construction

- **AEAD everywhere.** All encryption is authenticated, with associated data. Use vitaminc's AEAD API rather than calling a cipher directly; check docs.rs for which cipher the version in use provides.
- **Bind context with AAD.** Every ciphertext is sealed under a context that names where it lives, such as the tenant, table, or record (for example `"users/42/email"` or a labelled tuple of tenant and record), so it only opens there. Open under exactly the context you sealed under.
- **One type per purpose.** When a value is encrypted for more than one purpose (for example stored in the database and issued to clients), give each purpose its own type whose methods choose the context. Storage and client ciphertexts then never open under each other, and a caller cannot leave out a required binding.
- **Key rotation.** Store the key version or ID alongside the ciphertext; encrypt with the latest key, decrypt with the stored one.

## Keyed hashes and structured hashes

- **Blind indexes and equality terms:** use vitaminc's PRF with a context, not a hand-rolled keyed hash.
- **Hashing a secret:** use vitaminc's protected digest, so the input and output stay protected.
- **Domain separation:** every keyed hash or key derivation takes a fixed purpose string or context, so values derived for different purposes never collide.
- **Structured data outside vitaminc:** hash with `udigest` and `#[derive(udigest::Digestable)]`, never by concatenating fields.

```rust
// GOOD — udigest encodes field boundaries unambiguously
#[derive(udigest::Digestable)]
struct TokenClaim {
    user_id: String,
    scope: String,
}

let hash = udigest::hash::<sha2::Sha256>(&claim);

// BAD — ambiguous concatenation: ("ab", "c") hashes the same as ("a", "bc")
let mut hasher = Sha256::new();
hasher.update(user_id.as_bytes());
hasher.update(scope.as_bytes());
let hash = hasher.finalize();
```

## Errors at crypto boundaries

All cryptographic failures surface as one opaque error. Never expose internal crypto details at API boundaries.

```rust
// GOOD — one opaque error, no oracle-enabling distinctions
pub fn decode(s: &str) -> Result<Self, Unspecified> {
    let bytes = Base64UrlUnpadded::decode_vec(s).map_err(|_| Unspecified)?;
    let payload: Payload = rmp_serde::from_slice(&bytes).map_err(|_| Unspecified)?;
    Ok(Self { ciphertext: payload.ciphertext })
}

// GOOD — log details internally, return a generic error to the caller
let result = verify_token(token)
    .inspect_err(|e| tracing::warn!("{e}"))
    .map_err(|_| AuthError::Unauthorized("Unauthorized"))?;

// BAD — "bad padding" vs "bad MAC" vs "wrong key" is a padding oracle
pub fn decrypt(ct: &[u8]) -> Result<Vec<u8>, DecryptError> {
    match inner_decrypt(ct) {
        Err(BadPadding) => Err(DecryptError::BadPadding),  // oracle!
        Err(BadMac) => Err(DecryptError::BadMac),          // oracle!
        Ok(pt) => Ok(pt),
    }
}
```

- At HTTP boundaries, return generic errors (401, 403, 500) with no internal details.
- No error distinctions that enable oracles (padding, MAC, timing).
- Use `inspect_err` with `tracing::warn!` or `tracing::error!` to log details internally.
- For non-cryptographic library errors, follow the `thiserror` conventions in rust-sdk-dx; the opaque-error rule applies only at cryptographic and HTTP boundaries.

## Authentication

- **JWTs:** never enforce access based on unverified JWT claims. Peek at an unverified token only through a domain type such as `UnverifiedJwt` that makes the unverified status visible in the type system. All access-control decisions use a verified token.
- **Tokens at rest:** encrypt with vitaminc AEAD under a purpose-specific context, hold them in protected types, and expire them aggressively.
- **Stored credential secrets:** store only a slow password hash (for example `bcrypt`), never the secret or a fast hash of it.
- **Challenge verifiers** (PKCE and similar): hold in a protected type and compare in constant time.
- **Brute force:** rate-limit authentication endpoints.

## Random number generation

Generate every security-relevant random value through vitaminc (`SafeRand`, `Generatable`, `Protected::generate`); see the vitaminc skill or docs.rs for the current constructors and error handling.
Never use `thread_rng()` or `rand::random()` for secrets, and seed deterministically only in tests.
Build random secrets inside the protected type, so the raw bytes are never held unprotected.

## Serialization

For secret byte material that vitaminc does not serialize for you, use constant-time encoders. Never use standard hex or base64 encoders on secrets.

- `serdect`: constant-time serde for secret byte arrays and slices.
- `base16ct`: constant-time hex.
- `base64ct`: constant-time base64 (prefer `Base64UrlUnpadded`).
- Zeroize every intermediate buffer after encoding or decoding, on error paths too.
- Prefer MessagePack (`rmp_serde`) over JSON for binary key material.

Read [references/serialization.md](references/serialization.md) when writing `Serialize` / `Deserialize` or hex / base64 encoding for key material.

## Logging discipline

Never log secrets.

```rust
// GOOD — skip every argument in the span
#[instrument(skip_all)]
pub async fn create_access_key(
    connection: &mut AsyncPgConnection,
    cipher: &Cipher,
    key_name: &str,
) -> Result<AccessKey, AccessKeyError> { ... }

// GOOD — skip the arguments that hold or reach secrets
#[instrument(skip(conn, code))]
pub async fn redeem_device_code(
    conn: &mut AsyncPgConnection,
    code: &DeviceCode,
) -> Result<Token, Error> { ... }

// BAD — secret in log output
tracing::info!("Token: {}", token_str);
tracing::debug!("Key material: {:?}", key_bytes);
```

- Every secret type has a redacted `Debug` (`OpaqueDebug`, or `opaque_debug::implement!` where a derive cannot apply).
- Use `#[instrument(skip_all)]` or `#[instrument(skip(...))]` on functions taking secrets.
- Never interpolate secrets into `tracing` macros, `Display` output, or error messages.
