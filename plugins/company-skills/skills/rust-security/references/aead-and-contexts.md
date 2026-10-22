# AEAD and context binding with vitaminc

Worked examples for the rules in SKILL.md's "Cryptographic construction" section. They target vitaminc 0.5 (see "Versions" in SKILL.md).

## Contents

- [Encrypting with vitaminc](#encrypting-with-vitaminc)
- [Hand-written Encrypt and Decrypt](#hand-written-encrypt-and-decrypt)
- [AAD for context binding](#aad-for-context-binding)
- [Type-bound contexts](#type-bound-contexts)
- [Key rotation](#key-rotation)

## Encrypting with vitaminc

```rust
use vitaminc::encrypt::{Aes256Cipher, Encrypt};

let cipher = Aes256Cipher::new(&key)?;
// `&Aes256Cipher` is the `Cipher`; the result is an `AesCipherText` tree.
let ciphertext = value.encrypt_with_aad(&cipher, aad)?;
// The cipher opens it; the target type drives the structural decode.
let decrypted: Type = cipher.decrypt_with_aad(ciphertext, aad)?;
```

`Encrypt` / `Decrypt` are derivable for structs and newtypes (since vitaminc 0.3.0). Derive them by default.

## Hand-written Encrypt and Decrypt

Write the impls out only when the derive cannot apply:

- a newtype over a type that does not implement the traits, or
- a `ZeroizeOnDrop` newtype over a non-`Copy` field. The derive moves `self.0` out, which a `Drop` impl forbids.

`SecretToken` below is the second case. The wire shape is exactly what the derive would produce.

```rust
use vitaminc::aead::Decipher;
use vitaminc::encrypt::{Cipher, Decrypt, Encrypt, IntoAad};

impl Encrypt for SecretToken {
    fn encrypt_with_aad<'a, C, A>(mut self, cipher: C, aad: A) -> Result<C::Ok, C::Error>
    where
        C: Cipher,
        A: IntoAad<'a>,
    {
        // `take` moves the plaintext's heap buffer out of the ZeroizeOnDrop wrapper, so the
        // wrapper's drop no longer covers it: the `String` impl must zeroize its input after
        // sealing. Check that it does for your vitaminc version before copying this pattern.
        std::mem::take(&mut self.0).encrypt_with_aad(cipher, aad)
    }
}

impl<'c> Decrypt<'c> for SecretToken {
    fn decrypt_with_aad<'a, D, A>(decipher: D, aad: A) -> D::Ok<Self>
    where
        D: Decipher<'c>,
        A: IntoAad<'a>,
    {
        D::map_ok(String::decrypt_with_aad(decipher, aad), Self)
    }
}
```

## AAD for context binding

Bind ciphertext to its intended context using Additional Authenticated Data (AAD). A context is any `IntoContext` type. Since vitaminc 0.5, `IntoAad` and `IntoPrfContext` are blankets over `IntoContext`, so a domain type implements `IntoContext` once. A fixed byte tag already is one; implement `IntoContext` for domain values that should be bound.

`TenantId` here is an illustration: substitute your own identifier newtype.

```rust
use vitaminc::aead::{ContextPiece, IntoContext};

/// Context tag for tokens encrypted for database storage. `&[u8]` is
/// `IntoContext`, so the const is passed straight to `encrypt_with_aad`.
const STORAGE_CONTEXT: &[u8] = b"myapp-session-token-storage";

/// TenantId as a context — binds ciphertext to a specific tenant.
/// A tenant id is its text: the same context as the `&str` it renders to.
impl<'a> IntoContext<'a> for TenantId {
    fn into_context(self) -> ContextPiece<'a> {
        self.as_str().to_owned().into_context()
    }
}
```

Every leaf of a context is tagged with its type, so `"ctx"`, `b"ctx"` and a pre-encoded `Context` of the same bytes are three different contexts. Open under the same shape you sealed under.

## Type-bound contexts

Bind the purpose a value is encrypted for into its AAD, and let the type decide the purpose, so a caller cannot pick the wrong one or leave out what the purpose requires. The result: ciphertext sealed for storage never opens as a client token, and the reverse.

A typical split, for a token that is both stored and handed to clients:

- A bare token type has only a "seal for storage" method, which uses a fixed storage tag such as `STORAGE_CONTEXT` above.
- A separate type that pairs the token with the tenant (or other scope) it was issued for has only a "seal for client" method, which binds a different tag plus that tenant id.
- Converting between them is explicit (for example `token.with_tenant(tenant_id)`), so a client ciphertext cannot be produced without a tenant.

The method and type names below are your domain's own API, shown as an illustration of how the calls read, not vitaminc functions:

```rust
// Seal for storage — no tenant is known yet at this point in the flow
let column = token.encrypt_for_storage(&cipher)?.encode()?;

// Seal for a client — the tenant is part of the type, so it is always bound
let issued = token.with_tenant(tenant_id).encrypt_for_client(&cipher)?;

// A stolen DB record presented as a client token fails to open (desired)
let stolen = EncryptedSessionToken::decode(&column)?;
assert!(SessionTokenForTenant::decrypt_from_client(stolen, &cipher).is_err());
```

Test that cross-opening fails, as in the last line. vitaminc's `ContextTag` does the same fold at the AAD level for values that go through the generic `Encrypt` / `Decrypt` traits.

## Key rotation

- Store the key version or ID alongside the ciphertext.
- Encrypt with the latest key; decrypt with the key the stored version identifies.
