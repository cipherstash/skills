# Rust reviews ask before building any dependency change

Status: accepted, 2026-11-27

ADR 0002 lets a review run nothing that would run the change's code once the change touches its execution surface. In Rust, every compile runs build scripts and proc macros, including those of each dependency. A new or bumped crate is code the change brings in, and `cargo check` or clippy would run it.

So Rust's execution surface includes any added or changed dependency in `Cargo.toml` or `Cargo.lock`, as well as `build.rs`, proc-macro crates, `.cargo/config.toml`, `rust-toolchain.toml` and native objects. Compiles run offline. `rust-review` fetches its own tools only as prebuilt, checksum-verified binaries, never with `cargo install`, so nothing compiles on the reviewer's machine without a yes.

## Considered options

- **Only new dependencies, or bumps that add a build script.** Rejected: the review would have to inspect each crate's source to tell.
- **Trust dependencies once they are in the lockfile.** Rejected: a hijacked crate would run on the reviewer's machine.
- **`cargo install --locked` for tools.** Rejected: slow, and runs third-party build scripts.

## Consequences

Every Dependabot PR asks before clippy or tests run. Read-only tools (rustfmt, cargo-deny, cargo-shear, semgrep) still give evidence without asking.
