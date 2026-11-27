# The TypeScript check suite type-checks with TypeScript 7 and lints types with oxlint

Status: accepted, 2026-11-27

TypeScript 7, the Go-native compiler, has been the stable `typescript` package since 8 July 2026. It has no API for other tools until version 7.1. typescript-eslint, the usual type-aware linter, needs TypeScript below 6.1. So the TypeScript check suite runs `tsc --noEmit` on TypeScript 7, with a fixed `--checkers` count. Biome formats and runs the general lint rules. oxlint runs the type-aware rules, such as un-awaited promises and unsafe `any` values. The oxlint type-aware package's version moves with the TypeScript version, in the same PR.

The TypeScript grill on [#65](https://github.com/cipherstash/skills/issues/65) settled this decision, and [#145](https://github.com/cipherstash/skills/issues/145) recorded it.

## Considered options

- **TypeScript 6 with typescript-eslint.** Rejected: the suite would stay on the older compiler until typescript-eslint supports TypeScript 7, and its maintainers give no date.
- **TypeScript 7 for `tsc`, plus TypeScript 6 under an npm alias for typescript-eslint.** Rejected: two TypeScript versions can disagree about the same code.
- **Biome only.** Rejected: Biome's rule for un-awaited promises is still experimental.

## Consequences

The suite runs two lint tools with two configuration files. oxlint's type-aware mode was declared stable in July 2026, so it is younger than typescript-eslint. When typescript-eslint supports TypeScript 7, this decision can be revisited.
