# Behavior cases

This skill is a copy of `.claude/skills/vitaminc` in cipherstash/vitaminc, where every Rust block is doctested.
Change it there first, then copy it here unchanged.

## Should activate

- "Add an `ApiKey` type that we hold in memory and compare against the stored value." (in a Rust crate that depends on vitaminc)
- "Encrypt the user's email before writing it to Postgres."
- "Add a blind index so we can look users up by email without decrypting."
- "Generate a 20-character password for the new service account."
- "Wrap the data key under the root key before storing it."

## Should not activate

- "Hash this password in our TypeScript signup handler."
- "Add pagination to the `list_users` endpoint" in a Rust service, where no secret is touched.
- "Give this SDK's `Client` a typestate builder" — rust-sdk-dx, unless the client holds credentials.

## Expected behavior

- The agent reads the matching recipe in RECIPES.md before writing vitaminc code, and copies it as written.
- Secrets are wrapped in `Protected<T>` at the source and unwrapped with `risky_unwrap` / `risky_ref` only inside a call to an external API.
- Secret comparisons use `Equatable` or `TimingSafeEq`, never `==`.
- Every `encrypt` / `decrypt` call passes associated data naming the ciphertext's place, such as `"users/42/email"`.
- Every `prf_with_context` call names the index and its version, and writes and queries use the same input type and context.
- Randomness comes from `SafeRand`, never `rand::thread_rng` or `rand::random`; passwords are built inside `Protected::generate`, not with `vitaminc-password`.
- Keys are generated with `Key::random`, stored wrapped, and loaded with `Key::from_wrapped`; a hard-coded key appears only in tests.
- For APIs without a recipe, the agent checks docs.rs for the vitaminc version in `Cargo.toml` rather than guessing.
