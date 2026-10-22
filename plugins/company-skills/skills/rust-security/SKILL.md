---
name: rust-security
description: Applies CipherStash conventions for Rust code that handles secrets, cryptography, and authentication — the crate-level security lint block, secret types with OpaqueDebug, ZeroizeOnDrop and TimingSafeEq, opaque consuming-self design, constant-time comparison and encoding, vitaminc then aws-lc-rs then RustCrypto, AEAD with AAD context binding, blake3 domain separation, udigest for structured hashes, opaque Unspecified crypto errors, JWT verification, SafeRand, and logging discipline. Use when writing or changing Rust code that encrypts or decrypts, derives or stores keys, defines a token, key, password, or other secret type, compares or hashes secret values, generates security-relevant randomness, verifies credentials or JWTs, or serializes or logs data that may contain secrets. Does not apply to Rust code with no secret or crypto handling, non-Rust code, or general public API design, which rust-sdk-dx owns.
user-invocable: false
---

# Secure Rust Coding

When writing Rust code that handles secrets, cryptographic operations, or authentication, follow these conventions to prevent information leaks, side-channel attacks, and cryptographic misuse.

This skill owns the rules for secret types: redacted `Debug`, zeroization, constant-time comparison, and when `Clone` is allowed. For everything else about public library APIs (error enums, builders, derives, docs), follow the rust-sdk-dx skill in this plugin.

## Versions

The vitaminc examples target **vitaminc 0.5**: `IntoAad` and `IntoPrfContext` are blankets over `IntoContext`, and `SafeRand::next_below` replaces the deprecated `next_bounded_u32` (vitaminc-random 0.5). `Encrypt` / `Decrypt` have been derivable since 0.3.0.

Repositories on older pre-release vitaminc (for example `0.1.0-pre`) must upgrade before these examples compile. Check the repository's `Cargo.toml` first; if it pins an older vitaminc, say so and propose the upgrade instead of writing code that will not build.

**Ownership:** keep this skill in step with each vitaminc release. Update it through a pull request to `cipherstash/skills` alongside the vitaminc release that changes the API.

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

- `deny(unsafe_code)` — no unsafe allowed; use safe abstractions from vetted crates
- `clippy::mem_forget` — `mem::forget` bypasses `Drop`, defeating `ZeroizeOnDrop`
- `clippy::print_stdout/stderr/dbg_macro` — prevents accidental secret leaks to the console
- Test relaxations are `cfg_attr(test, ...)` so they don't weaken production code

## Secret types and memory safety

Derive `OpaqueDebug` and `TimingSafeEq` from `vitaminc`, and `ZeroizeOnDrop` from `zeroize`, for types holding secrets.

```rust
// GOOD — secrets are zeroed on drop, opaque in debug, compared in constant time
use vitaminc::protected::{OpaqueDebug, TimingSafeEq};
use zeroize::ZeroizeOnDrop;

#[derive(OpaqueDebug, ZeroizeOnDrop, TimingSafeEq)]
pub struct SecretToken(String);

// GOOD — OpaqueDebug works on both struct and tuple forms
#[derive(OpaqueDebug, ZeroizeOnDrop, TimingSafeEq)]
pub struct Verifier([u8; 32]);

// GOOD — skip non-secret fields from zeroization
#[derive(Zeroize, ZeroizeOnDrop)]
pub struct ClientKey {
    #[zeroize(skip)]
    pub key_id: Uuid,
    pub keyset: V1KeySet,
}

// BAD — secrets linger in memory, visible in debug output
#[derive(Debug, Clone)]
pub struct ApiKey(String);
```

- `OpaqueDebug` prints `"***"` instead of the actual value — prevents log leaks
- `ZeroizeOnDrop` overwrites memory with zeros when the value goes out of scope
- `TimingSafeEq` provides constant-time equality — prevents timing attacks on comparisons
- Use `#[zeroize(skip)]` on fields that are not secret (IDs, metadata)
- Zeroize intermediate buffers after encoding (see Serialization below)
- Avoid deriving or implementing `Clone` on secret types unless there is a clear, documented need (e.g., cheap copies of small, short-lived tokens); when `Clone` is required, minimize the number of clones and ensure all copies are protected by `ZeroizeOnDrop` or equivalent
- Avoid `Serialize`/`Deserialize` on raw secret types unless the ser/de is constant-time

## Opaque secret type design

Secret types should be opaque wrappers that prefer consuming (move) semantics:

```rust
// GOOD — opaque wrapper, consuming self, internal-only access
#[derive(OpaqueDebug, ZeroizeOnDrop, TimingSafeEq)]
pub struct Verifier([u8; 32]);

impl Verifier {
    // Consumes self — the original is moved, then zeroized via the new owner
    pub fn encode(self) -> EncodedVerifier {
        EncodedVerifier(Base64UrlUnpadded::encode_string(&self.0))
    }
}

// GOOD — pub(crate) accessor for internal code that needs the raw value
impl Verifier {
    pub(crate) fn as_bytes(&self) -> &[u8] {
        &self.0
    }
}

// BAD — AsRef bypasses TimingSafeEq, allows callers to use == on the inner value
impl AsRef<[u8]> for Verifier {
    fn as_ref(&self) -> &[u8] {
        &self.0
    }
}

// BAD — Deref exposes the inner value implicitly
impl Deref for Verifier {
    type Target = [u8];
    fn deref(&self) -> &[u8] { &self.0 }
}
```

- Do NOT implement `AsRef`, `Deref`, or similar on types deriving `TimingSafeEq` — it bypasses constant-time comparison by exposing the raw value for `==`
- Prefer consuming `self` (move) over `&self` — preserves zeroization guarantees, avoids copies
- Public API accepts and returns the opaque wrapper; only internal code touches raw data
- If internal access is needed, use `pub(crate)` methods, not public traits

## Constant-time operations and side channels

Use `TimingSafeEq` (vitaminc) for all secret comparisons. Never use `==` or `PartialEq` on secrets.

```rust
// GOOD — constant-time comparison
use vitaminc::protected::TimingSafeEq;

if submitted.timing_safe_eq(&stored) {
    // accept
}

// GOOD — constant-time selection with subtle crate
use subtle::{Choice, ConditionallySelectable, ConstantTimeEq};

let should_record = is_diff & not_found_yet;
diff_x = u8::conditional_select(&diff_x, x, should_record);

// BAD — early return leaks which byte differed
fn compare(a: &[u8], b: &[u8]) -> bool {
    for (x, y) in a.iter().zip(b.iter()) {
        if x != y { return false; }  // timing leak!
    }
    true
}
```

- **Cache:** never use secret values as array or map indices — cache timing reveals the index. Prefer hardware-accelerated AES (via `aws-lc-rs`), which uses constant-time AES-NI instructions.
- **Memory:** use `ZeroizeOnDrop` for all secret types and call `.zeroize()` explicitly on intermediate buffers after use. For `Copy` types, rely on the volatile writes the `zeroize` crate performs.
- **Compiler:** `zeroize` uses volatile writes to prevent dead-store elimination; `mem::forget` bypasses `Drop`, which `clippy::mem_forget` catches.
- **Speculative execution:** keep secret-dependent branches to a minimum; prefer `ConditionallySelectable` over `if/else` on secret values.

Zeroize hasher state after finalization:

```rust
// GOOD — intermediate hasher state zeroized
let mut hasher = blake3::Hasher::new();
hasher.update(b"MYAPP-INDEXKEY");
hasher.update(&rect);
let key: Key = {
    let mut key = Key::default();
    hasher.finalize_xof().fill(&mut key);
    key
};
hasher.zeroize();

// BAD — hasher state with key-derived data left in memory
let hash = hasher.finalize();
// hasher still contains internal state
```

## Crypto library preference

1. **`vitaminc`** (uses `aws-lc-rs` internally) — for encryption and decryption, through its `Encrypt` / `Decrypt` traits. Derive them; hand-write only when the derive cannot apply.
2. **`aws-lc-rs`** — for direct primitive needs (FIPS-validated, hardware-accelerated).
3. **RustCrypto crates** (`sha2`, `hmac`, `aes-gcm-siv`, etc.) — acceptable fallback.
4. **Never** implement primitives from scratch.

## Cryptographic construction

- **AEAD everywhere.** All encryption uses authenticated encryption with associated data. Prefer AES-256-GCM-SIV (nonce-misuse resistant). vitaminc's `Encrypt` / `Decrypt` enforce this.
- **Bind context with AAD.** Pass an `IntoContext` value as AAD so ciphertext only opens in the context it was sealed for. A fixed byte tag (`const STORAGE_CONTEXT: &[u8] = b"...";`) already is one; implement `IntoContext` once on domain identifiers (such as a `TenantId`) that must be bound. Open under the same context shape you sealed under — `"ctx"`, `b"ctx"`, and a pre-encoded `Context` of the same bytes are three different contexts.
- **Let the type fix the AAD purpose.** When a value is encrypted for more than one purpose (for example, stored in the database and issued to clients), give each purpose its own type whose methods choose the AAD, so storage and client ciphertexts never open under each other and a caller cannot leave out a required binding.
- **Key rotation.** Store the key version or ID alongside the ciphertext; encrypt with the latest key, decrypt with the stored one.

Read [references/aead-and-contexts.md](references/aead-and-contexts.md) when encrypting a type, hand-writing `Encrypt` / `Decrypt` (for example on a `ZeroizeOnDrop` newtype over a `String`), implementing `IntoContext`, or designing purpose-bound token types. It has the vitaminc code for each.

### Domain separation with blake3

Use fixed info strings so keys derived for different purposes never collide:

```rust
// GOOD — domain-separated key derivation
let mut hasher = blake3::Hasher::new();
hasher.update(b"MYAPP-INDEXKEY");  // fixed domain string
hasher.update(&key_material);
hasher.finalize_xof().fill(&mut derived_key);
hasher.zeroize();

// GOOD — keyed blake3 with domain string for MACs; every variable-length field is
// length-prefixed and integers are fixed-width, so field boundaries are unambiguous
let mut mac = blake3::Hasher::new_keyed(key);
mac.update(b"device_code")  // domain string
    .update(&(user_code_bytes.len() as u64).to_le_bytes())
    .update(user_code_bytes)
    .update(&expires_at_secs.to_le_bytes());
mac.finalize_xof().fill(&mut output);
mac.zeroize();
```

### Unambiguous encoding for hashes and MACs

When hashing structured data, use `udigest` with `#[derive(udigest::Digestable)]` to prevent ambiguous concatenation attacks where `H(a || b) == H(a' || b')`:

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

vitaminc handles unambiguous encoding for AAD automatically; for general hash or MAC operations on structured data, use `udigest` explicitly.

## Errors at crypto boundaries

Use `Unspecified` for cryptographic errors. Never expose internal crypto details at API boundaries.

```rust
// GOOD — generic Unspecified error, no oracle-enabling distinctions
pub fn decode(s: &str) -> Result<Self, Unspecified> {
    let bytes = Base64UrlUnpadded::decode_vec(s).map_err(|_| Unspecified)?;
    let payload: Payload = rmp_serde::from_slice(&bytes).map_err(|_| Unspecified)?;
    Ok(Self { ciphertext: payload.ciphertext })
}

// GOOD — inspect_err + tracing for internal observability without leaking to caller
let result = verify_token(token)
    .inspect_err(|e| tracing::warn!("{e}"))
    .map_err(|_| AuthError::Unauthorized("Unauthorized"))?;

// BAD — different errors for "bad padding" vs "bad MAC" vs "wrong key" = padding oracle
pub fn decrypt(ct: &[u8]) -> Result<Vec<u8>, DecryptError> {
    match inner_decrypt(ct) {
        Err(BadPadding) => Err(DecryptError::BadPadding),  // oracle!
        Err(BadMac) => Err(DecryptError::BadMac),          // oracle!
        Ok(pt) => Ok(pt),
    }
}
```

- All crypto operation failures return the same opaque error type (`Unspecified`)
- At HTTP boundaries, return generic errors (401, 403, 500) — no internal details
- No error distinctions that enable oracles (padding oracle, timing oracle)
- Use `inspect_err` + `tracing::error!`/`tracing::warn!` to log details internally
- For non-cryptographic library errors, follow the `thiserror` conventions in the rust-sdk-dx skill in this plugin. The `Unspecified` pattern applies only at cryptographic operation boundaries

## Authentication

- **JWTs:** never enforce access based on unverified JWT claims. Peeking at an unverified token is acceptable only through a domain type such as `UnverifiedJwt` that makes the unverified status visible in the type system. All access-control decisions use a verified token.
- **Tokens at rest:** encrypt with vitaminc `Encrypt` / `Decrypt` and purpose-specific AAD, derive `ZeroizeOnDrop`, and expire aggressively — short-lived tokens shrink the window of compromise.
- **Stored credential secrets:** store only a slow password hash (for example `bcrypt`), never the secret or a fast hash of it.
- **Challenge verifiers** (PKCE and similar): derive `TimingSafeEq` and compare with `timing_safe_eq`.
- **Brute force:** rate-limit authentication endpoints.

## Random number generation

Use `SafeRand` from vitaminc for all security-critical random values. Never use `thread_rng()` for cryptographic purposes.

- Always `SafeRand::from_entropy()` for production random values
- Use `SafeRand::from_seed([...])` only in tests, for deterministic output
- Implement the `Generatable` trait for custom types that need random construction
- Use `next_below(n)` for uniform selection from `0..n`

## Serialization

Use constant-time serialization for secret data. Never use standard hex or base64 encoders on secrets.

- `serdect` — constant-time serde for secret byte arrays and slices
- `base16ct` — constant-time hex encoding and decoding
- `base64ct` — constant-time base64 encoding and decoding (prefer `Base64UrlUnpadded`)
- Always zeroize intermediate buffers after encoding or decoding
- Prefer MessagePack (`rmp_serde`) over JSON for binary key material

Read [references/randomness-and-serialization.md](references/randomness-and-serialization.md) when generating random secrets, implementing `Generatable`, migrating from `next_bounded_u32`, or writing `Serialize` / `Deserialize` or hex/base64 encoding for key material.

## Logging discipline

Never log secrets. Use `OpaqueDebug` and `#[instrument(skip(...))]` to prevent accidental leaks.

```rust
// GOOD — OpaqueDebug prevents {:?} from leaking the value
#[derive(OpaqueDebug, ZeroizeOnDrop)]
pub struct SecretToken(String);
// format!("{:?}", token) => "***"

// GOOD — opaque_debug::implement! for non-derive cases
opaque_debug::implement!(DataKey);
// format!("{:?}", data_key) => "DataKey { ... }"

// GOOD — skip sensitive arguments in tracing spans
#[instrument(skip_all)]
pub async fn create_access_key(
    connection: &mut AsyncPgConnection,
    cipher: &Aes256Cipher,
    key_name: &str,
) -> Result<AccessKey, AccessKeyError> { ... }

#[instrument(skip(conn, code))]
pub async fn redeem_device_code(
    conn: &mut AsyncPgConnection,
    code: &DeviceCode,
) -> Result<Token, Error> { ... }

// BAD — secret in log output
tracing::info!("Token: {}", token.as_str());
tracing::debug!("Key material: {:?}", key_bytes);
```

- Every secret type uses `OpaqueDebug` (derive) or `opaque_debug::implement!()` (macro)
- Use `#[instrument(skip_all)]` or `#[instrument(skip(field))]` on functions taking secrets
- Use `inspect_err` + `tracing::error!`/`tracing::warn!` for internal diagnostics
- Never interpolate secrets into `tracing::info!`, `tracing::debug!`, `Display` output, or error messages
