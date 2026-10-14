# Patching by ecosystem

Read the section for the issue's ecosystem. Every section follows the same escalation ladder. Stop at the first rung after which the fix check exits 0; SKILL.md's evidence gate (gate.py) still decides the outcome, and it fails on any `unsupported` lockfile. A binary `bun.lockb` cannot be read, so a repo that has one is **blocked** until a human converts it to a text `bun.lock`. Never delete a lockfile to regenerate it.

1. **In-range update.** Refresh the resolved version without touching any manifest. This works when every dependent's version range already admits the fix.
2. **Manifest bump.** Raise the requirement where deps.py's `manifests` shows the package declared directly, then reinstall.
3. **Parent bump.** For a transitive dependency, update the dependent that pins the old version. Find it with the ecosystem's "why" command.
4. **Override.** Force the resolution with the ecosystem's override mechanism, scoped to the vulnerable range so other major lines are left alone. Use this only when rungs 1–3 cannot reach the target. Say why in the PR body, because an override has to be removed later.

Stop and report **blocked** when:
- the target version does not exist in the registry (Vanta's fixed version is occasionally wrong or ahead of publication)
- reaching the target needs a direct dependency to cross more than one major line
- the bump needs source changes

A direct dependency crossing exactly one major line (0.x minor counts as major) is allowed, as a **draft** PR.

Move as little as possible. Take the lowest release that meets the target, not the latest. Pull in only the extra upgrades the target forces. A bump that drags sibling packages to their newest releases can raise the minimum toolchain: in Rust, `rust-version` in `Cargo.toml` or `rust-toolchain.toml`; in npm, `engines`. A raised minimum breaks builds that the lockfile check won't catch. When the ecosystem command overshoots, pin each forced upgrade to its lowest compatible version (`cargo update -p <dep> --precise <lowest>`), and say in the PR body which extra packages moved and why.

Run commands in the directory that holds the lockfile, once per lockfile deps.py listed. Use the package manager version the repo pins: `packageManager` in package.json via corepack, `rust-toolchain.toml`, or the `go` directive.

## Contents

- [npm family: pnpm, npm, yarn, bun](#npm-family-pnpm-npm-yarn-bun)
- [Rust: cargo](#rust-cargo)
- [Go](#go)
- [Python: poetry, uv, pip, pipenv](#python-poetry-uv-pip-pipenv)
- [PHP: composer](#php-composer)

## npm family: pnpm, npm, yarn, bun

Tell the manager by its lockfile:
- `pnpm-lock.yaml` is pnpm.
- `package-lock.json` is npm.
- `yarn.lock` is yarn: Berry when the file has a `__metadata:` block, classic otherwise.
- `bun.lock` is bun.

Confirm the target exists first: `npm view <pkg>@<target> version`.

| Rung | pnpm | npm | yarn | bun |
| -- | -- | -- | -- | -- |
| 1 | `pnpm update -r <pkg>` | `npm update <pkg>` | classic: `yarn upgrade <pkg>`; berry: `yarn up -R <pkg>` | `bun update <pkg>` |
| 2 | Edit the spec. A `catalog:` spec lives in `pnpm-workspace.yaml` under `catalog:` or `catalogs.<name>:`. Then `pnpm install`. | Edit the spec, then `npm install` | Edit the spec, then `yarn install` | Edit the spec, then `bun install` |
| why | `pnpm why -r <pkg>` | `npm explain <pkg>` | `yarn why <pkg>` | `bun pm why <pkg>` (newer bun) or read `bun.lock` |
| 4 | `"<pkg>@<vulnerable range>": "^<target>"` under `overrides:` in `pnpm-workspace.yaml` if the repo already keeps overrides there, else under `pnpm.overrides` in the root package.json. Then `pnpm install`. | `overrides` in the root package.json, then `npm install` | `resolutions` in the root package.json, then `yarn install` | `overrides` in the root package.json, then `bun install` |
| check | `pnpm install --frozen-lockfile --ignore-scripts` | `npm install --package-lock-only --ignore-scripts`, then confirm `git diff` shows no further change | berry: `yarn install --immutable`; classic: `yarn install --frozen-lockfile --ignore-scripts` | `bun install --frozen-lockfile` |

Notes:
- A package that appears under several major lines needs the fix only on the vulnerable lines. Scope an override to the vulnerable range (`"brace-expansion@>=2.0.0 <2.1.7": "^2.1.7"`) rather than forcing every copy to one version.
- An existing override for the package may be what holds it back. If deps.py lists an `overrides`, `resolutions`, or `pnpm.overrides` entry pinning an older version, raise that entry first.
- Don't add `--force`, `--legacy-peer-deps`, or `--no-frozen-lockfile` to make an install succeed. A peer conflict that blocks the bump is a **blocked** outcome; report the conflict.

## Rust: cargo

Confirm the target exists first: `cargo info <pkg>@<target>`, or `cargo search <pkg> --limit 1` for the latest version.

- **Rung 1:** `cargo update -p <pkg>@<current> --precise <target>`. Include `@<current>` when the lockfile holds several versions of the package, as deps.py shows.
- **Rung 2:** for a requirement in `Cargo.toml` (a `[workspace.dependencies]` entry or a crate's `[dependencies]`), raise it, then run `cargo update -p <pkg>`.
- **Why:** `cargo tree -i <pkg>@<current> -e all --locked`.
- **Rung 3:** when `--precise` fails with "failed to select a version" because a dependent requires `=x.y.z` or an older 0.x line, run `cargo update -p <dependent> --precise <version that admits the fix>`. Repeat up the chain.
- **Rung 4:** `[patch.crates-io]` is not an override for this purpose. It redirects sources and does not relax requirements, so it can't help. When rung 3 fails, the outcome is **blocked**: name the dependent and the release that would unblock it.
- **Check:** `cargo metadata --locked --format-version 1 > /dev/null`. It fails if `Cargo.lock` no longer matches the manifests.
- **Toolchain floor:** when the workspace declares `rust-version` or pins a toolchain, check each newly resolved crate's `rust-version` with `cargo info <crate>@<version>`, and choose lower versions of any crate that exceeds it.

Nested `Cargo.lock` files are separate workspaces with their own lockfiles, such as `fuzz/` or an FFI package under a JS tree. Dependabot reports each one, so patch each one.

## Go

Each `go.mod` is its own module. Run commands in its directory.

- **Confirm** the target exists: `go list -m <module>@v<target>`.
- **Rungs 1–2:** `go get <module>@v<target>`, then `go mod tidy`. A `/vN` module path is a different module: crossing that line is a major bump.
- **Why:** `go mod why -m <module>`, and `go mod graph | grep <module>`.
- **Rung 4:** a `replace` directive is not an acceptable override for a security bump. Report **blocked** instead.
- **Check:** `go mod tidy` leaves no further diff, and `go mod verify` passes.

## Python: poetry, uv, pip, pipenv

Confirm the target exists first: `pip index versions <pkg>`, or the PyPI JSON API at `https://pypi.org/pypi/<pkg>/json`.

- **poetry**
  - Rung 1: `poetry update <pkg>`.
  - Rung 2: raise the constraint in `pyproject.toml`, then run `poetry lock`. On Poetry 1.x, use `poetry lock --no-update` instead.
  - Check: `poetry check --lock`.
- **uv**
  - Rung 1: `uv lock --upgrade-package <pkg>`.
  - Rung 2: raise the constraint in `pyproject.toml`, then run `uv lock`.
  - Check: `uv lock --check`.
- **requirements files:** edit the `==` pin.
- **pipenv**
  - Update: `pipenv update <pkg>`.
  - Check: `pipenv verify`.

Test-only Python environments, such as a `tests/python/poetry.lock`, are still reported by Dependabot and still get patched.

## PHP: composer

- **Rung 1:** `composer update <pkg> --with-dependencies`.
- **Rung 2:** raise the constraint in `composer.json`, then rerun rung 1.
- **Why:** `composer why <pkg>`.
- **Check:** `composer validate --no-check-publish`.
