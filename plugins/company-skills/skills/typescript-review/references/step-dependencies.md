# Step: dependency management

Area 9, medium priority. Read this, and typescript-practices' `references/dependencies.md`, before reviewing changes to `package.json` dependency fields, `pnpm-lock.yaml`, `pnpm-workspace.yaml`, `.npmrc`, or imports of packages. The practices reference holds the rules and the pnpm settings. This file says what to look for, how to get evidence without installing anything, and what is not a finding. The review never installs the change's dependencies, as `checks.md` says.

## Contents

- [What to report](#what-to-report)
- [Reading the lockfile](#reading-the-lockfile)
- [Known vulnerabilities](#known-vulnerabilities)
- [Severity](#severity)
- [Not a finding](#not-a-finding)

## What to report

- **A tool not pinned exactly**: a devDependency that is a tool, above all one of the TypeScript check suite, added or changed with a caret or tilde range, a tag such as `latest`, or `*`. typescript-practices pins each tool at an exact version. A pair of tools that must match, such as `vitest` and `@vitest/coverage-v8`, can then install at different versions. When CI runs that tool and the change unpins it, the check is weakened: report it once, under testing and coverage, as `checks.md` says under "The check suite in CI".
- **`package.json` and the lockfile out of step**: a dependency added, removed, or moved in `package.json` with no matching change to `pnpm-lock.yaml`, or the reverse. `pnpm install --frozen-lockfile` then fails in CI. A second lockfile, `package-lock.json` or `yarn.lock`, beside `pnpm-lock.yaml`.
- **A lockfile change the `package.json` change does not explain**: a package or version that moved with no dependency change asking for it, or many packages updated in one change with no reason given.
- **Install scripts and exotic sources**: a new entry in `allowBuilds` with no comment saying why; `strictDepBuilds` or `blockExoticSubdeps` turned off; a dependency from a git or tarball URL, which has no registry version and no release age and can run code during install.
- **Release age**: `minimumReleaseAge` lowered below 1440 or removed, or a `minimumReleaseAgeExclude` entry with no comment, or one left after its version is old enough.
- **Overrides**: an `overrides` entry with no comment naming the advisory it fixes, or one that pins a package to a version with a known vulnerability.
- **The wrong field**: a tool, test library, or type package in `dependencies` of a published package, so every user installs it; a runtime import of a package that is only in `devDependencies`, which fails for users; a framework the user must provide in `dependencies` instead of `peerDependencies`.
- **A new dependency where Node already does the job**, such as `node-fetch` for `fetch`, `uuid` for `crypto.randomUUID`, or a deep-clone package for `structuredClone`; or one that is unmaintained, brings many packages with it, or has an install script, with no reason in the change.
- **`packageManager` changed** with no reason, or removed.

A removed dependency, a raised major version, or a raised minimum of a peer dependency can break users: report that consequence under breaking changes.

## Reading the lockfile

Read `pnpm-lock.yaml` at the base and the head with `git show`, as text. Compare the `importers` entry for each changed package with its `package.json`: each specifier there must match the one in `package.json`. Never run `pnpm install`, `pnpm install --lockfile-only`, or `pnpm why`, which resolve and can fetch.

## Known vulnerabilities

osv-scanner checks every lockfile against the OSV database, which it reads over the network from `osv.dev`. `checks.md` runs it only when the user allows the network. Otherwise record it as not run, with the command the user can run: `osv-scanner scan source -r .`. Quote CI's osv-scanner result for the head commit when there is one.

When it runs, report each vulnerability in a package the change adds or moves to an affected version as a finding, with its ID, the package and version, and the fixed version. Vulnerabilities in packages the change does not touch go under the checks as context: they are not caused by the change. Without osv-scanner, review a change that adds or updates a dependency by reading: name the package and version, and say the vulnerability check is a limit.

## Severity

- `critical`: a known vulnerability in a package the change adds or updates, in code the package calls with untrusted input.
- `major`: a known vulnerability with no shown path from untrusted input; a lockfile out of step with `package.json`, which fails every frozen install; a git or tarball dependency, or an install script approved with no reason.
- `minor`: a tool not pinned exactly; a dependency in the wrong field with no shown failure; a new dependency where Node already does the job.

## Not a finding

- An available update with no fix, vulnerability, or reason behind it.
- A caret range on a runtime dependency of a published library, which lets its users share one copy. The lockfile still fixes what CI tests.
- A lockfile entry that changes only because pnpm rewrote it for a dependency change in the same commit.
- A vulnerability check that could not run. That is a limit.
