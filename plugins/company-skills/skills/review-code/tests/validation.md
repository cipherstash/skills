# Port validation record

## Executed

- `python3 scripts/validate.py`: passed, 20 skills in the initial shared workspace; 19 skills on the independent PR branch (the separate plain-language port is excluded).
- `python3 -m unittest discover -s scripts/tests`: passed, 23 tests.
- Each of review-audit and review-cross-check's existing Python suites: passed, 9 tests each.
- `git diff --check`: passed.
- Claude Code 2.1.323: `claude plugin validate . --strict` and `claude plugin validate plugins/company-skills --strict` passed. The latter also reported a non-failing catalog warning for the existing missing plugin icon.

An independent Codex agent read the new instructions and reviewed a scratch git fixture with tracked TypeScript/test/Python edits and an untracked prose file. It used sequential specialist passes and a hashed working snapshot. The exact Codex host version and model were not exposed.

The fixture's test suite passed 1/1. A numeric JSON name caused an observed TypeError through an unchecked TypeScript assertion. A separate scratch mutation returning a constant wrong greeting still passed the weakened assertion. The review produced two distinct findings, merged the related negative-test gap into the runtime defect, retained sources and snapshot identity, and raised no finding for benign Python os.path usage. The reviewed snapshot remained unchanged. The exercise found a routing/scope mismatch for standalone JavaScript; review-typescript now explicitly includes JavaScript runtime review.

An independent integration pass checked the final entry point, findings contract, test-gap skill, and four downstream workflows. It found no blocking handoff contradiction after the verifier and coverage-fix changes.

The independent PR worktree initially selected Homebrew Python 3.14, which lacked PyYAML and could not import the workflow tests. Re-running with the existing mise Python 3.13 environment (the CI version, with PyYAML installed) passed all 41 tests listed above. No dependencies were installed.

## Simulated or unavailable

Documentation-only routing, failed-delegate retry, and a host without subagents were instruction walkthroughs, not induced host-failure tests. The scratch review did not exercise actual parallel scheduling or remote PR cross-check/post/audit/fix actions.

A fresh Claude Code 2.1.323 invocation with the local plugin and read-only tools was attempted. It returned `Not logged in · Please run /login` before API execution. No Claude runtime behavior or slash-command discovery is claimed. The Codex CLI was unavailable on PATH; fresh installed-plugin picker discovery was not tested. The independent Codex fixture review used explicit skill file reads, not installed skill discovery.

Before release, refresh the plugin in authenticated fresh Codex and Claude sessions, confirm the seven added skills are discoverable, and exercise their prompts plus the downstream handoff cases. Structural checks and this fixture are not substitutes for those host tests.
