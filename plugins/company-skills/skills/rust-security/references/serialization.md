# Constant-time serialization for secrets

Worked examples for SKILL.md's "Serialization" rules, for secret byte material that vitaminc does not serialize for you.
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
