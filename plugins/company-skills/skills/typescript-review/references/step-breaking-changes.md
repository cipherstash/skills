# Step: breaking changes

Area 11, low priority. Read this, and typescript-practices' `references/project-structure.md` (its sections on the `exports` map, `isolatedDeclarations`, publint, and attw) and `references/dependencies.md` (its section on adding a dependency), before comparing what the package offers its users at the base and the head. Packaging defects belong here too: a package that installs but does not load breaks its users the same way an API change does. This file says how to find the changes with publint, attw, and a comparison of the declaration files, what counts as breaking, and when a version bump is needed.

## Contents

- [What is public](#what-is-public)
- [Evidence](#evidence)
- [What breaks users](#what-breaks-users)
- [Version bump](#version-bump)
- [Report](#report)
- [Not a finding](#not-a-finding)

## What is public

A package is published when its `package.json` does not set `"private": true`. Its public API is:

- every export of every entry point its `exports` map names, followed through `export *` and `export { … } from`, with the types of each; with no `exports` map, its `main`, `module`, and `types` files and every file in its `files` list;
- the `exports` map itself: its subpaths and their conditions;
- `name`, `type`, `engines.node`, `bin`, and the `dependencies` and `peerDependencies` its users install.

A private package has no users outside the repository: a change to it breaks only the repository's own code, which the correctness area reviews. A module no entry point exports, and test files, are not API.

## Evidence

Use all three, by the first way each can run.

1. **The declaration comparison.** Emit the declaration files of each changed published package at the base and at the head, each in its own worktree made as `target.md` describes, and compare them, as `checks.md` gives the command. It writes only to a temporary directory and runs none of the change's code. It needs the change's dependencies, as `tsc --noEmit` does, so it is usually a limit. Then compare by reading: list every public export at the base and the head with `git show <base>:<path>` and the head files. Reading gives the same declarations only when step 3 recorded `isolatedDeclarations` on for the package: then every export states its type in the source. Without it, an export's type can be inferred, such as a return type left unstated, and a change to an inferred type does not show in the source. Record each such export as a limit of the API comparison. Pair a removed and an added export with the same shape as a rename.
2. **publint** (`publint --strict`) reports `exports` entries that point at missing files, a wrong `type`, and files the package leaves out. **attw** (`attw --pack .`, with `--profile esm-only` for an ESM-only package) reports types that resolve differently from the code under each module resolution. Both need a built package, so a build runs first: that is the execution surface and needs the change's dependencies, so both are usually limits. Quote CI's publint and attw results for the head commit instead, when there are any.
3. **`package.json`**: read it at the base and the head, and compare every field under [What is public](#what-is-public).

## What breaks users

- An export removed or renamed, including one an `export *` stopped passing on, or a subpath removed from `exports`.
- A function's parameters changed: one added without a default, one removed when callers pass it, or a type narrowed. A return type widened, such as `string` to `string | undefined`, or a result union given a new failure that callers' exhaustive checks do not handle.
- A type changed so that values callers build no longer fit: a required field added to a type callers construct, a union member removed, an optional field made required.
- A class's method or property removed, made `private`, or changed in type; a required constructor parameter added.
- An `exports` map added to a package that had none, so imports of any other path stop working; a condition removed, such as `require` or `types`; `type` changed between `module` and `commonjs`.
- `engines.node` raised, a peer dependency's minimum raised, or a dependency removed that users import through the package.
- Behaviour a user relies on that the documentation promised: report it as a correctness finding and mention it here.

Additions are not breaking: a new export, a new optional parameter, a new optional field in a type callers build, a new subpath.

## Version bump

Read the package's `version` at the base. Look for a version bump in the change: a higher `version` in `package.json`, or a changeset file under `.changeset/` that names the package with `major`, `minor`, or `patch`.

- At `1.0.0` or later, a breaking change needs a major version. Without one, every user who updates within the range they depend on, such as `^1.4.0`, breaks.
- Below `1.0.0`, a breaking change needs the minor version bumped, since a caret range on `0.x` does not cross a minor version. Say that users still break if they update by hand, and that the release notes should name the change.
- With no version found, treat the package as `1.0.0` or later, and say in the finding that it is minor below `1.0.0`.

## Report

Each breaking change is a finding, located at the deleted line at the base, or the changed line at the head:

- `major` at `1.0.0` or later, or at an unknown version, with no major version bump; or when code elsewhere in the repository stops compiling.
- `minor` below `1.0.0`, or when the package has no users outside the repository and says so.

A packaging defect that publint or attw shows, such as an `exports` entry pointing at a file the build does not emit, is `major`: the package does not load for its users. When the review cannot compare the API, record that as a limit.

## Not a finding

- A change to a private package, a module no entry point exports, or a test file.
- An addition, as above.
- A breaking change that the change already marks with the right version bump.
- A widened parameter type or a narrowed return type, which every existing caller still accepts.
