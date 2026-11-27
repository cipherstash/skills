# New TypeScript packages publish ESM only

Status: accepted, 2026-11-27

Node's guide to [publishing a package](https://nodejs.org/en/learn/modules/publishing-a-package) says it is generally best to publish one module format, because publishing both formats can load two copies of one package. CommonJS code can load an ESM package with `require` since Node 22.12, unless the package, or a module it imports, uses top-level `await`. Then `require` throws `ERR_REQUIRE_ASYNC_MODULE` ([Node's modules docs](https://nodejs.org/api/modules.html#loading-ecmascript-modules-using-require)). An ESM-only package therefore works for CommonJS users only when it has no top-level `await`. So `typescript-practices` tells the authors of new packages to publish ESM only, with no top-level `await`. A repository with its own rule keeps it, such as a repository whose agent instructions require both `import` and `require` exports. Where a package publishes both formats, [Are the Types Wrong](https://arethetypeswrong.github.io) (attw) checks that TypeScript finds the right types for both formats. attw does not run either format's code.

The TypeScript grill on [#65](https://github.com/cipherstash/skills/issues/65) settled this decision, and [#145](https://github.com/cipherstash/skills/issues/145) recorded it.

## Considered options

- **ESM and CommonJS everywhere.** Rejected: every package builds twice, and users can load two copies.
- **ESM only everywhere.** Rejected: repositories that publish both formats today would have to change their published packages.

## Consequences

`typescript-practices` and some repositories' own rules give different defaults. A review follows the repository's rule.
