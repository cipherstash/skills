# Dependencies

How to add, pin, and install dependencies: pnpm, a committed lockfile, a frozen install, release-age and install-script settings, and osv-scanner. The rules target TypeScript 7.0, Node 24, and pnpm 11 or later, whose settings they name. The [examples package](../examples/package.json) follows them.

## pnpm

- Use pnpm. Pin its version in the root `package.json`'s `packageManager` field, such as `"packageManager": "pnpm@12.23.0"`. Corepack and `pnpm/action-setup` read it, so everyone runs the same pnpm.
- A repository with several packages is one pnpm workspace, listed in `pnpm-workspace.yaml`. Depend on another package in it with `workspace:*`, not a version or a path.
- Run a tool with `pnpm exec`, from the devDependency that the lockfile pins. Do not run `npx <tool>` or `pnpm dlx <tool>` without an exact version: it fetches whatever is newest, past the lockfile and its integrity hashes.

## The lockfile and the frozen install

- Commit `pnpm-lock.yaml`. Keep one lockfile per workspace, and no `package-lock.json` or `yarn.lock` beside it.
- Install in CI with `pnpm install --frozen-lockfile`. It installs exactly what the lockfile records, and fails if `package.json` and the lockfile disagree.
- Change the lockfile only with pnpm, in the same commit as the `package.json` change that needs it. Review its diff: a new package, or a version that moved, is part of the change.
- Pin each tool, a devDependency, at an exact version, as [checks.md](checks.md) says. A published library may give its runtime dependencies a caret range, so its users can share one copy. The lockfile still fixes what CI tests.

## Release-age and install-script settings

pnpm reads these settings from `pnpm-workspace.yaml`. From [`pnpm-workspace.yaml`](../examples/pnpm-workspace.yaml):

```yaml
# Install no version published less than a day ago (in minutes). Setting it
# makes the check strict: a newer version fails the install.
minimumReleaseAge: 1440
# Fail the install when a dependency has an install script that allowBuilds
# does not approve.
strictDepBuilds: true
# Install no git or tarball URL dependency of a dependency.
blockExoticSubdeps: true
```

- **Release age**: `minimumReleaseAge` holds back a version for a time after it is published, so a compromised release is usually found and removed before it is installed. Set it in every repository, to at least 1440 minutes. A repository may wait longer, such as 10080 minutes, a week. pnpm checks it when it resolves versions and when it verifies the lockfile.
- An exception goes in `minimumReleaseAgeExclude`, such as an urgent security fix. Give each entry a comment saying why, and remove it once the version is old enough.
- **Install scripts**: pnpm runs no dependency's `preinstall`, `install`, or `postinstall` script unless `allowBuilds` approves it, as `esbuild: true`. With `strictDepBuilds`, a script no one has decided on fails the install, instead of being skipped without notice. Approve a script only when the package cannot work without it, and say why in a comment. `allowBuilds` replaced `onlyBuiltDependencies` in pnpm 11.
- **Exotic dependencies**: a git or tarball URL dependency has no registry version, no release age, and can run code during install. `blockExoticSubdeps` refuses one anywhere below a direct dependency.
- To force a transitive dependency to a fixed version, add it to `overrides` in `pnpm-workspace.yaml`. Comment each override with the advisory it fixes, such as its GHSA ID, and remove it once the parent depends on a fixed version.

## osv-scanner

- CI runs `osv-scanner scan source -r .` over every lockfile in the repository. It fails on any known vulnerability, as [checks.md](checks.md) says.
- Fix a finding by moving to a fixed version: update the direct dependency, or add an override for a transitive one. #110 decides how to suppress an advisory that has no fixed version.

## Adding a dependency

- Prefer what Node has built in, such as `fetch`, `AbortSignal`, `structuredClone`, the `crypto` module, and `parseArgs` from the `util` module.
- Before you add a package, check that it is maintained, how many packages it brings with it, whether it has an install script, and that its licence allows the use.
- A runtime dependency of a published package goes in `dependencies`. A tool goes in `devDependencies`. A package the user must install alongside, such as a framework, goes in `peerDependencies`.
- Removing a dependency, raising its major version, or raising a peer dependency's minimum can break users. Treat it as a breaking change, as [project-structure.md](project-structure.md) says.
