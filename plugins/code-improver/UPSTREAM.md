# Upstream

This folder is a copy of the `code-improver` plugin from [Trail of Bits' skills repository](https://github.com/trailofbits/skills), taken from `plugins/code-improver` at commit `149d7b21f4067765b82e67029730b42d228ef4b4`. It is published by Trail of Bits under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) (see `LICENSE`), not this repository's MIT licence.

## Changes from upstream

- Left out `tests/` and `evals/`. `tests/fixtures/` holds three fake plugins, each with its own `.claude-plugin/plugin.json`, and Claude Code refuses to install or update a plugin with a `plugin.json` below its root. The README still lists both folders.
- Added this file and `LICENSE`, the upstream repository's licence.

Every other file is unchanged. `scripts/check_pinned_sources.py` checks that, by comparing this folder with upstream at the commit above.

## Why a copy

Until 2026-11-26 the `company` catalog listed `code-improver` as a `git-subdir` source pinned to the same commit. A `git-subdir` source ships the whole folder, so the fixtures came with it and updating the plugin failed. No upstream commit leaves the fixtures out. When Trail of Bits moves them, replace this folder with a `git-subdir` entry again.

## Moving to a newer upstream commit

1. Review the upstream changes to `plugins/code-improver` since the commit above.
2. Copy the upstream folder at the new commit over this one, without `tests/` and `evals/`.
3. Change the commit in this file and in `VENDORED` in `scripts/check_pinned_sources.py`.
4. Run `python3 scripts/check_pinned_sources.py`.
