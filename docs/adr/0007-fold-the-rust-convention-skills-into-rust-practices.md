# Fold the Rust convention skills into rust-practices

Status: accepted, 2026-11-27

Rust had three convention skills before the language skills process existed: `rust-sdk-dx`, `rust-security` and `rust-testing`. They predate the practices rules: no check suite, no examples crate, no script test, and references longer than 100 lines. CONTRIBUTING exempted Rust until a `rust-practices` skill existed.

We fold the three into `rust-practices` as references, and rewrite them to meet the practices rules. `rust-practices` owns all Rust knowledge, as CONTRIBUTING requires of every practices skill, and `rust-review` reads only `rust-practices`.

## Considered options

- **Add `rust-practices` beside the three, linking to them by name.** Rejected: four skills to keep consistent, and CONTRIBUTING would need a rule letting a practices skill route topics to other skills.
- **No practices skill; `rust-review` reads the three as they are.** Rejected: Rust would have no check suite, no examples, and no rules for ownership, async, `unsafe` or dependencies.

## Consequences

The three released names become deprecated aliases for one release, under **Renaming a skill**. Their content is audited and rewritten like upstream material. Other skills that name them are updated in the release ticket.
