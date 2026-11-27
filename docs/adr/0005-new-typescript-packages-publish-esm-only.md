# New TypeScript packages publish ESM only

Status: accepted, 2026-11-27

Node advises publishing one module format. CommonJS code can load an ESM package with `require` since Node 22.12, so an ESM-only package still works for CommonJS users. Publishing both formats can load two copies of one package. So `typescript-practices` tells the authors of new packages to publish ESM only. A repository with its own rule keeps it, such as a repository whose agent instructions require both `import` and `require` exports. Where a package publishes both formats, attw checks that both work.

The TypeScript grill on [#65](https://github.com/cipherstash/skills/issues/65) settled this decision, and [#145](https://github.com/cipherstash/skills/issues/145) recorded it.

## Considered options

- **ESM and CommonJS everywhere.** Rejected: every package builds twice, and users can load two copies.
- **ESM only everywhere.** Rejected: repositories that publish both formats today would have to change their published packages.

## Consequences

`typescript-practices` and some repositories' own rules give different defaults. A review follows the repository's rule.
