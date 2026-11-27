# Rust's check suite has conditional checks

Status: accepted, 2026-11-27

Go's suite applies the same checks to every module. Rust crates differ more: some contain `unsafe`, some are published, some have features or declare a minimum Rust version. Checks such as Miri or cargo-semver-checks matter for those crates and make no sense for the rest.

Rust's suite has conditional checks. Each is triggered by a crate property that `checks.md` names: Miri for `unsafe`, cargo-semver-checks and a publish dry run for published crates, a minimum-version build for a declared `rust-version`, and cargo-hack for features. Where the property holds and the check is not in place, the review reports a missing-check line.

## Considered options

- **Require them for every crate.** Rejected: Miri and semver checks make no sense for most crates.
- **Advice only, outside the suite.** Rejected: the review would never notice a crate with `unsafe` and no Miri.

## Consequences

`rust-review` must detect each property. Another language may adopt the pattern later; this ADR covers only Rust.
