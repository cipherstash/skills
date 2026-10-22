# Behavior cases

This is a background convention skill: it is applied while the agent writes code, not invoked by name.

## Should activate

- "Add a `Client` type to this crate's public API with a builder for the endpoint, timeout, and credentials."
- "Our SDK returns `Box<dyn Error>`; give it a proper error type." (in a Rust library crate)
- "Make this crate nicer to use from other projects" in a Rust library with no other detail — the agent asks which public surface to change, or proposes one, rather than rewriting everything.

## Should not activate

- "Add a `--verbose` flag to the CLI binary" in a Rust application crate with no library surface.
- "Write a TypeScript wrapper for this API."
- "Store this access token encrypted at rest" — secret handling is rust-security's job, though both may apply to a public secret type.

## Expected behavior

- Public error enums use `thiserror`, are `#[non_exhaustive]`, carry context, and never use `anyhow` or `Box<dyn Error>` in the public API; library code returns `Result` instead of panicking.
- Structs with more than two configuration fields get a builder; required fields are enforced by a typestate builder and `build()` returns `Result`.
- Public types derive `Debug` and the other traits the skill lists where appropriate; domain identifiers are newtypes.
- Signatures accept `impl Into<T>` / `impl AsRef<T>` and avoid `&String` and `&Vec<T>`; boolean parameters become two-variant enums.
- Every public item has a doc comment; key items have a compilable `# Examples` section and fallible functions an `# Errors` section.
- Optional dependencies sit behind feature flags with `default = []`.
- For types holding secrets, the agent follows rust-security rather than inventing its own redaction or `Clone` policy.
- The agent does not invent crate names, modules, or types that are not in the user's codebase.
