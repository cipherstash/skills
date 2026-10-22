# Randomness and serialization for secrets

Worked examples for SKILL.md's "Random number generation" and "Serialization" rules. They target vitaminc 0.5 (vitaminc-random 0.5 for `next_below`).

## Contents

- [Random number generation](#random-number-generation)
- [Constant-time serialization](#constant-time-serialization)

## Random number generation

```rust
use vitaminc::{Generatable, SafeRand};

// GOOD — SafeRand backed by a CSPRNG
let mut rng = SafeRand::from_entropy();
let verifier = Verifier::random(&mut rng)?;

// GOOD — bounded random for character selection: `next_below(n)` draws from `0..n`
let char_idx = rng.next_below(CHARSET.len() as u32);

// GOOD — implement Generatable for custom types. Indexing the charset with the random
// value is acceptable only because the table is tiny (one cache line), so the lookup
// leaks nothing through cache timing; never index larger tables with secret values.
impl Generatable for UserCode {
    fn random(rng: &mut SafeRand) -> Result<Self, RandomError> {
        let mut code = ArrayString::new();
        iter::repeat_with(|| {
            let char = rng.next_below(STANDARD_CHARS.len() as u32);
            STANDARD_CHARS[char as usize]
        })
        .take(CODE_LEN)
        .for_each(|char| code.push(char));
        Ok(Self(code))
    }
}

// BAD — thread_rng is not guaranteed to be a CSPRNG on all platforms
use rand::thread_rng;
let key: [u8; 32] = thread_rng().gen();
```

`next_below(n)` replaces `next_bounded_u32`, whose bound was inclusive and which is deprecated in vitaminc-random 0.5. When migrating, check each call site for an off-by-one: `next_bounded_u32(n - 1)` becomes `next_below(n)`.

## Constant-time serialization

`V1KeySet` and `KeySet` below stand for any wrapper around secret key material.

```rust
// GOOD — serdect for constant-time hex serialization
impl Serialize for V1KeySet {
    fn serialize<S>(&self, serializer: S) -> Result<S::Ok, S::Error>
    where
        S: Serializer,
    {
        let mut bytes = self.0.to_bytes().map_err(serde::ser::Error::custom)?;
        let result = serdect::slice::serialize_hex_lower_or_bin(&bytes, serializer);
        bytes.zeroize();  // zeroize the intermediate copy of the key
        result
    }
}

impl<'de> Deserialize<'de> for V1KeySet {
    fn deserialize<D>(deserializer: D) -> Result<Self, D::Error>
    where
        D: Deserializer<'de>,
    {
        let mut buffer = [0; 168];
        let result = serdect::array::deserialize_hex_or_bin(&mut buffer, deserializer)
            .and_then(|_| KeySet::from_bytes(&buffer).map_err(serde::de::Error::custom));
        buffer.zeroize();  // zeroize on every path, including errors, before returning
        result.map(Self)
    }
}

// GOOD — base16ct/base64ct for constant-time encoding
use base16ct::lower;
use base64ct::{Base64UrlUnpadded, Encoding};

let hex = base16ct::lower::encode_string(&bytes);
let b64 = Base64UrlUnpadded::encode_string(&bytes);

// GOOD — zeroize intermediates after encoding
pub(crate) fn to_hex(&self) -> Result<String> {
    self.0.to_bytes().map(|mut bytes| {
        let hex = base16ct::lower::encode_string(&bytes);
        bytes.zeroize();
        hex
    })
}
```
