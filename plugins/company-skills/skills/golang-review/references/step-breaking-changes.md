# Step: breaking changes

Area 10, low priority. Read this, and golang-practices' `references/dependencies.md` (its section on major versions) and `references/project-structure.md` (its sections on `internal` packages and the `go.mod` file), before comparing the exported API of the base and the head. This file says how to find the API changes without fetching anything, what counts as breaking, and when a version bump is needed.

## Contents

- [What is public](#what-is-public)
- [Compare the exported API](#compare-the-exported-api)
- [What breaks importers](#what-breaks-importers)
- [Version bump](#version-bump)
- [Report](#report)
- [Not a finding](#not-a-finding)

## What is public

The public API is every exported identifier in a non-`internal`, non-`main` package of the module, plus the module path itself. Code under `internal/` is public only inside the module, so changing it breaks nothing outside. Test files are not API.

## Compare the exported API

Compare each changed public package at the base and the head, by the first of these that works:

1. **`apidiff`**, when already installed (`command -v apidiff`). Read `apidiff -help` first for its arguments on that version. It reports incompatible and compatible changes separately. Never install it.
2. **`go doc -all <package>`**, run in the head worktree and in a base worktree. Make the base worktree as `target.md` describes, at the base commit, with hooks and LFS downloads off. `go doc` reads source and runs none of it, so the base needs no reading first. Collect every declaration it prints: each line that starts with `func`, `type`, `const`, or `var`; each name in a grouped `const (` or `var (` block, which prints one tab-indented line per name; and the struct fields and interface methods under each type. Before comparing the two sets, collapse runs of spaces, since `gofmt` realigns a group when a longer name joins it, and drop parameter, result, and receiver names, since renaming one changes no importer: `func (this T) M(a int)` and `func (t T) M(b int)` are the same declaration. A declaration only at the base is removed or changed; one only at the head is added or changed. Pair a removed and an added declaration with the same shape as a rename. A package that exists only at the base is removed whole: every exported declaration in it is removed.
3. **Reading**, when no go command can run: list the exported declarations the diff deletes or changes with `git show <base>:<path>` and the head files.

Also compare the `module` line in `go.mod`: a changed module path breaks every importer.

## What breaks importers

- An exported identifier, method, or struct field removed or renamed, including one name in a grouped `const` or `var` block.
- A function signature changed: a parameter added, removed, or retyped; a result added or retyped. Making a parameter variadic still breaks code that stores the function in a variable of the old type.
- A method added to an exported interface, which breaks every implementation outside the package.
- A type changed in kind, such as a struct to an interface, or a field's type changed.
- A field added to a struct that importers build with an unkeyed literal, or a field that is not comparable, such as a slice or map, added to a struct importers compare with `==`.
- A constant's value or a sentinel error changed where importers compare with it.
- Behaviour an importer relies on that the documentation promised: report that as a correctness finding and mention it here.

Additions are not breaking: a new function, a new method on a concrete type, a new field in a struct importers build with keyed literals.

## Version bump

Find the module's version. Every command here only reads.

1. A module path ending in a major-version suffix (`/v2` and above) is at that version or later. That settles it.
2. Otherwise read its latest release tag: `git tag --list 'v*' --sort=-v:refname` (or `<dir>/v*` for a module in a subdirectory). A shallow clone, a clone of a fork, or a pull request fetched by its ref can lack the tags, so finding none locally does not mean `v0`. When the clone has a remote, list the tags there too: `git ls-remote --tags <repository URL> 'v*'`, with the PR's repository URL or `origin`. A repository with no remote has only its local tags.
3. No suffix and no tag in either place: the module has no release, which Go treats as `v0`. Tags that cannot be read, such as an `ls-remote` that fails, leave the version unknown: record that as a limit.

- At `v1` or later, a breaking change needs a new major version: a `/vN+1` module path and every internal import changed with it. Without one, every importer that updates breaks.
- At `v0`, Go makes no compatibility promise. Note that importers still break, and that the change should be named in the release notes and the minor version bumped.
- At an unknown version, treat the module as `v1` or later, and say in the finding that it is minor if the module is at `v0`.

## Report

List every removed, renamed, or changed exported declaration under `API changes` in the report, as `output.md` shows, with the version note. Each breaking one is also a finding, located at the deleted line at the base, or the changed line at the head:

- `major` at `v1` or later, or at an unknown version, with no major-version bump, or when an importer in the same repository stops compiling.
- `minor` at `v0`, or when the module has no importers outside the repository and says so.

When the review cannot compare the API, record that as a limit.

## Not a finding

- A change to an `internal` package, a `main` package, or a test file.
- An added identifier or method on a concrete type.
- A breaking change that the change already handles with a new major version.
