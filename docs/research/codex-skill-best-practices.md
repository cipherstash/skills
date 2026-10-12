# Codex plugin and skill audit

Date: 2026-10-09. Baseline: `origin/main` at `4d9e829`.

## Verdict

The checked-in package structure is configured correctly for Codex. No manifest relocation, duplicated skills, or release version change is needed. This audit supersedes the scaffold-only assessment from 2026-09-22.

## Verified structure

- The Codex marketplace is `.agents/plugins/marketplace.json`, named `company`, with a local source at `./plugins/company-skills`, display metadata, install/authentication policy, and category.
- The portable manifest declares Agent Plugins 1.0. The Codex compatibility manifest points to `./skills/`. There is no `extensions.com.openai` override that would shadow the compatibility metadata. This matches [OpenAI's packaging guidance](https://developers.openai.com/plugins/build/plugins).
- Portable, Codex, and Claude manifests agree on name, version (`0.1.0`), description, publisher, and license. Both catalogs resolve to the same plugin directory.
- Three canonical skill directories contain entrypoints and behavior cases: `address-code-review`, `audit-pr-feedback`, and `cross-check-review-findings`. Their linked resources exist within their own skill directories.
- `address-code-review/agents/openai.yaml` disables implicit invocation in Codex; its Claude frontmatter has the corresponding explicit-only setting. The other skills need no Codex metadata file. See [Codex invocation policy](https://learn.chatgpt.com/docs/build-skills#optional-metadata).
- The workflows support sequential execution when subagents are unavailable. PR feedback scripts document Python and authenticated `gh` prerequisites.

## Corrections made

- README now includes Codex remote/local installation, skill discovery, refresh instructions, prerequisites, and a skill inventory. CLI syntax was checked with installed `codex-cli 0.160.0` help; desktop instructions follow the packaging guide.
- CONTRIBUTING and AGENTS now cover Codex invocation policy, host verification, installation pointers, and alignment of all three manifests.
- The validator now catches broken Codex skill paths, missing marketplace policy/category/display metadata, incorrect marketplace identity/source type, missing publisher metadata, absent skills, and a portable OpenAI extension shadowing the compatibility manifest. Packaging regression tests run in CI.
- Removed the obsolete claims that no skills exist and Codex metadata is undocumented.

## Verification and limits

Run from the repository root:

```sh
python3 scripts/validate.py
python3 -m unittest discover -s scripts/tests
python3 -m unittest discover -s plugins/company-skills/skills/audit-pr-feedback/tests
python3 -m unittest discover -s plugins/company-skills/skills/cross-check-review-findings/tests
claude plugin validate . --strict
claude plugin validate plugins/company-skills --strict
```

Validation passed for all three skills. All 10 packaging regression tests and all 10 existing PR feedback script tests passed. Both Claude strict manifest checks and `git diff --check` passed.

This is a structural and documentation audit, not an end-to-end installation or behavioral evaluation. No plugin was installed into the user's configuration, no PR feedback was posted, and live prompt cases were not executed in either host. The validator enforces repository conventions; it is not a full upstream schema validator, particularly for optional `agents/openai.yaml` fields. Use CONTRIBUTING's host checks before claiming runtime compatibility.
