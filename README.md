# Company agent skills

Reusable company workflows published as [open Agent Skills](https://agentskills.io) for Codex and Claude Code. One plugin, `company-skills`, ships every skill from the `company` marketplace in this repository.

## Install

Both products install at user scope by default, so the skills are available in every project.

Both products cache the plugin by version, so updates arrive only when a release bumps the plugin version (see [Releases](CONTRIBUTING.md#releases)).

### Claude Code

```sh
claude plugin marketplace add cipherstash/skills
claude plugin install company-skills@company
```

Installing company-skills also installs and enables six plugins as dependencies: the Trail of Bits `differential-review` and `insecure-defaults` plugins (see [Bundled Trail of Bits plugins](#bundled-trail-of-bits-plugins)), and the `golang-pro`, `python-pro`, `rust-engineer` and `typescript-pro` language skills (see [Bundled language practice skills](#bundled-language-practice-skills)).

Inside a session, `/plugin marketplace add cipherstash/skills` and `/plugin install company-skills@company` do the same. Start a new session, then invoke a skill by its namespaced name, for example `/company-skills:review-fix`.

To update to the latest published skills, refresh the marketplace, update the plugin, then start a new session:

```sh
claude plugin marketplace update company
claude plugin update company-skills@company
```

Updating company-skills does not update its dependencies. When a release moves the pinned commit of a bundled plugin, update that plugin by name as well:

```sh
claude plugin update differential-review@company
claude plugin update insecure-defaults@company
claude plugin update golang-pro@company
claude plugin update python-pro@company
claude plugin update rust-engineer@company
claude plugin update typescript-pro@company
```

### Codex

```sh
codex plugin marketplace add cipherstash/skills --ref main
codex plugin add company-skills@company
codex plugin add differential-review@company
codex plugin add insecure-defaults@company
codex plugin list --marketplace company
```

Codex does not install plugin dependencies, so add the two Trail of Bits plugins explicitly (see [Bundled Trail of Bits plugins](#bundled-trail-of-bits-plugins)). The command syntax was checked against `codex-cli 0.169.0`. Start a fresh session and use `/skills` or type `$` to select an installed skill, then supply its inputs. Skills can also match requests automatically.

If your CLI does not provide `plugin add`, restart the desktop app, choose **Company** in the Plugins Directory, and install **Company Skills** there. See [OpenAI’s plugin packaging guide](https://developers.openai.com/plugins/build/plugins) for marketplace configuration.

To update, refresh the marketplace, then reinstall the plugin:

```sh
codex plugin marketplace upgrade company
codex plugin remove company-skills@company
codex plugin add company-skills@company
```

## Bundled Trail of Bits plugins

The `company` marketplace also lists two plugins from [Trail of Bits' skills repository](https://github.com/trailofbits/skills), so accounts and routines that cannot add the Trail of Bits marketplace still get them:

| Plugin | Provides |
| --- | --- |
| `differential-review` | The `differential-review` skill, the `/differential-review:diff-review` command, and the `adversarial-modeler` agent: a security-focused review of a PR, commit, or diff |
| `insecure-defaults` | The `/insecure-defaults:audit` command and its `audit-pipeline` workflow: an audit for fallback secrets, default credentials, fail-open switches, weak crypto, permissive access, and debug leakage |

Both entries are `git-subdir` sources pinned to one full upstream commit SHA. No upstream files are copied into this repository. They are published by Trail of Bits under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), not this repository's MIT licence.

- **Claude Code:** company-skills declares both as dependencies, so `claude plugin install company-skills@company` installs and enables them. Checked with Claude Code 2.1.327.
- **Codex:** both plugins install from the same pinned entries, but Codex has no plugin dependencies, so install each with `codex plugin add` as shown under [Codex](#codex). `insecure-defaults` ships a Claude Code command and workflow and no `skills/` directory, so it may expose nothing in Codex. Checked with `codex-cli 0.169.0`.

Nothing auto-updates them: a plugin with a pinned `sha` stays on that commit through marketplace refreshes and plugin updates. To move the pin, open a pull request that:

1. Reviews the upstream changes to `plugins/differential-review` and `plugins/insecure-defaults` since the current SHA.
2. Changes `sha` for both entries in `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` to the same new full 40-character commit SHA. The validator fails when the two catalogs differ or a SHA is not a full commit.
3. Bumps the plugin version in all three manifests, as described in [Releases](CONTRIBUTING.md#releases).

## Bundled language practice skills

The `company` marketplace also lists four language skills from [Jeffallan's claude-skills repository](https://github.com/Jeffallan/claude-skills), each as its own plugin:

| Plugin | Provides |
| --- | --- |
| `golang-pro` | The `golang-pro` skill, with references on concurrency, interfaces, generics, testing, and project structure |
| `python-pro` | The `python-pro` skill, with references on async patterns, packaging, the standard library, testing, and the type system |
| `rust-engineer` | The `rust-engineer` skill, with references on async, error handling, ownership, testing, and traits |
| `typescript-pro` | The `typescript-pro` skill, with references on advanced types, configuration, patterns, type guards, and utility types |

They are reference material on language practice. Upstream wrote them for writing code, not reviewing it, so their descriptions also match requests to write Go, Python, Rust, or TypeScript.

Upstream publishes all 67 of its skills as one plugin. Each entry here installs one skill instead: a `git-subdir` source pointing at that skill's directory, `skills/<name>`, with `"strict": false` and `"skills": ["./"]` so the directory loads as a plugin holding a single skill. All four are pinned to the commit of the upstream v0.4.20 release. No upstream files are copied into this repository. They are published by Jeffallan under the MIT licence.

- **Claude Code:** company-skills declares all four as dependencies, so `claude plugin install company-skills@company` installs and enables them. Invoke one by its namespaced name, for example `/golang-pro:golang-pro`. Checked with Claude Code 2.1.328.
- **Codex:** the Codex catalog does not list them, and they have not been tested there.

Nothing auto-updates them. To move the pin, open a pull request that:

1. Reviews the upstream changes to the four skill directories since the current SHA.
2. Changes `sha` for all four entries in `.claude-plugin/marketplace.json` to the same new full 40-character commit SHA.
3. Bumps the plugin version in all three manifests, as described in [Releases](CONTRIBUTING.md#releases).

Installed users receive the new commit only when they update each of the four plugins by name, as shown under [Claude Code](#claude-code).

## Develop locally

Install from a clone by passing its path instead of `cipherstash/skills`. Use one source for the `company` marketplace at a time; cloning alone does not install the plugin:

```sh
claude plugin marketplace add /path/to/skills
claude plugin install company-skills@company

codex plugin marketplace add /path/to/skills
codex plugin add company-skills@company
```

Both products install a cached copy, so edits in the clone are not live:

- **Claude Code:** run `claude plugin marketplace update company`, then `claude plugin update company-skills@company`, and start a new session. If a change still does not appear, bump the plugin version in all three manifests as described in [Releases](CONTRIBUTING.md#releases). To test edits without reinstalling, start a session with `claude --plugin-dir /path/to/skills/plugins/company-skills`.
- **Codex:** `marketplace upgrade` refreshes Git marketplaces only. For a local clone, run `codex plugin remove company-skills@company`, then `codex plugin add company-skills@company`, and start a new session.

## Structure

```text
.
├── .agents/plugins/marketplace.json       # Codex marketplace
├── .claude-plugin/marketplace.json        # Claude Code marketplace
└── plugins/company-skills/
    ├── plugin.json                         # Portable Agent Plugins manifest
    ├── .codex-plugin/plugin.json           # Codex compatibility metadata
    ├── .claude-plugin/plugin.json          # Claude Code plugin metadata
    └── skills/<skill-name>/SKILL.md        # Shared skill source
```

Each skill is authored once under `plugins/company-skills/skills/`. The portable manifest discovers `skills/`; the Codex compatibility manifest explicitly points to `./skills/`; Claude Code uses the same directory. Marketplace source paths resolve from the repository root, and plugin resource paths resolve from `plugins/company-skills/`.

## Available skills

| Skill | Purpose | Invocation |
| --- | --- | --- |
| `review-code` | Review a PR or diff through selected specialist agents, then hand findings to cross-check and posting | Explicit or automatic |
| `review-test-gaps` | Find missing regression protection and ineffective test assertions | Selected by review-code, or focused request |
| `review-infracode` | Review infrastructure lifecycle, permissions, deployment, CI, and observability risks | Selected by review-code, or focused request |
| `review-golang` | Review Go semantics, concurrency, errors, and API compatibility | Selected by review-code, or a request naming a specific concern |
| `review-typescript` | Review TypeScript/JavaScript boundaries, types, async behavior, and compatibility | Selected by review-code, or a request naming a specific concern |
| `review-rust` | Review Rust safety, async behavior, APIs, and applicable company conventions | Selected by review-code, or a request naming a specific concern |
| `review-python` | Review Python state, exceptions, async behavior, packaging, and test validity | Selected by review-code, or a request naming a specific concern |
| `review-audit` | Audit existing PR feedback against the PR head | Explicit or automatic |
| `review-cross-check` | Verify new findings and report which are new against existing PR feedback | Explicit or automatic |
| `review-post` | Post review findings to a PR with source-tagged inline comments and a review attestation | Explicit or automatic |
| `review-fix` | Verify findings and fix confirmed defects | Explicit or automatic |
| `run-report` | Log every problem an unattended run hits and publish a run report as a Claude artifact | Explicit or automatic |
| `vanta-triage` | Reconcile open Vanta vulnerability findings with Linear issues: file, retarget, refresh, realign, reopen, and close | Explicit or automatic |
| `vanta-remediate` | Build the Remediate queue from Todo Vanta Linear issues, patch dependencies, verify every lockfile, and open PRs | Explicit or automatic |
| `rust-sdk-dx` | Conventions for public Rust APIs in libraries and SDKs | Automatic while writing Rust library code |
| `rust-security` | Rules for Rust code that handles secrets, cryptography, and authentication | Automatic while writing Rust that touches secrets |
| `rust-testing` | Conventions for Rust tests: nextest, scenario modules, fake data, mocktail, paused time | Automatic while writing Rust tests |
| `golang-wazero` | Lessons from real bugs in Go programs that embed the wazero WebAssembly runtime, for review and writing | Automatic while reviewing or writing Go code that uses wazero |
| `filing-github-issues` | Draft and file well-structured GitHub issues on CipherStash repos | Explicit or automatic |
| `authoring-pull-requests` | Branch, commit, and open draft pull requests with a consistent structure | Explicit or automatic |
| `plain-language` | Write, rewrite, and review prose in plain language (ISO 24495 and GOV.UK), with a bundled checker | Explicit or automatic |

Start a fresh review with `review-code`. It pins the diff or working snapshot, selects the applicable lower-level review skills, delegates them through the host's agents, and combines supported findings with their evidence and sources. Hosts without subagents use the same skills sequentially. No separate agent setup, model matrix, or external review runner is needed.

In Claude Code, use `/company-skills:review-code <PR URL or comparison>`. In Codex, select the installed `company-skills` `review-code` skill from `/skills` or the `$` picker and provide the target.

A general request to review changes goes to `review-code`, whatever the language. Calling a language specialist directly reviews only that language: it skips `review-test-gaps`, `review-infracode` and the cross-check handoff.

For PRs, `review-code` passes findings to `review-cross-check` unless raw review alone was requested. `review-post` publishes the resulting postable set when asked. Receiving agents use `review-audit` to check existing feedback against the current head and `review-fix` to verify and fix outstanding findings. A review request alone does not post or fix anything. Local dirty reviews remain identified as snapshots until verified against a PR head.

The six specialist capabilities are independently authored adaptations informed by an [audit of auxesis/junk pr-review](plugins/company-skills/skills/review-code/references/upstream-audit.md). The audit records the pinned source, omitted infrastructure, and corrected source assumptions.

The four language specialists also read language practice references from Jeffallan's `golang-pro`, `python-pro`, `rust-engineer` and `typescript-pro` skills, which the `company` marketplace bundles as pinned plugins. Each specialist names the reference to read for each changed area and keeps its own review rules where a reference disagrees. Without the bundled skill installed, a specialist reviews from its own instructions and reports the missing references as a coverage limit.

Convention skills (`rust-*` and `golang-wazero`) carry coding rules rather than a workflow. Claude Code applies them automatically and hides them from the `/` menu; Codex selects them implicitly.

`review-audit` and `review-cross-check` require Python 3, Git, and `gh` authenticated for the target repository; `review-post` requires `gh` and `python3` or `jq`. These are local CLI dependencies; the plugin does not bundle an MCP server.

The Vanta skills also need the Linear connector, read-only Vanta API credentials (`vanta-api.all:read`) with network access to `api.vanta.com` for `vanta-triage`, either as an environment network secret of type OAuth 2.0 client credentials for `api.vanta.com` or as `VANTA_CLIENT_ID` and `VANTA_CLIENT_SECRET`, and each target ecosystem's toolchain (`cargo`, `pnpm`/`npm`/`yarn`/`bun`, `go`, `poetry`/`uv`) for `vanta-remediate`. `vanta-remediate` also needs the GitHub MCP server for pull requests and `git` push access to the target repos; it does not use the `gh` CLI. Both run unattended, so they suit Claude Code routines.

`plain-language` is ported from [auxesis/plain-language-skill](https://github.com/auxesis/plain-language-skill) under the Apache License 2.0; its `LICENSE` and `NOTICE` files carry the licence, the Open Government Licence credit for the GOV.UK material, and the changes made here. The port ships the skill and its checker, `scripts/check.py`, which needs Python 3.9 or later and no packages. It does not ship the upstream plugin's hooks, which add the rules to every session and send back chat replies that break them; install that plugin separately if you want them.

`run-report` publishes through Claude's Artifact tool; on a host without it, the report goes in the run's final message. List it first in a routine's prompt so it logs problems from the start of the run, for example:

```text
/company-skills:run-report Code review
/company-skills:review-code <PR URL>
/company-skills:review-post
```

### Removed aliases

0.10.0 removes the explicit-only aliases left by the 0.8.0 rename of the code review skills. Invoke the new names instead: `review-fix` for `address-code-review`, `review-audit` for `audit-pr-feedback`, and `review-cross-check` for `cross-check-review-findings`. `review-cross-check` ends at a report; `review-post` publishes the findings.

## Contribute

Follow [CONTRIBUTING.md](CONTRIBUTING.md) to add or change a skill: naming, progressive disclosure, required behavior cases, releases, and the validation commands to run. Pull requests run `python3 scripts/validate.py`, `python3 -m unittest discover -s scripts/tests`, and each skill's `tests/` suite in GitHub Actions; the `claude plugin validate --strict` checks run locally only.

See the official [Codex skills documentation](https://developers.openai.com/codex/skills/) and [Claude Code plugin marketplace documentation](https://code.claude.com/docs/en/plugin-marketplaces) for current publishing and installation options.

## License

The repository is licensed under the MIT License; see [LICENSE](LICENSE).

`plugins/company-skills/skills/plain-language` is licensed under the Apache License 2.0, and some of its content is public sector information under the Open Government Licence v3.0. See its [LICENSE](plugins/company-skills/skills/plain-language/LICENSE) and [NOTICE](plugins/company-skills/skills/plain-language/NOTICE). The plugin manifests declare the combined SPDX expression `MIT AND Apache-2.0 AND OGL-UK-3.0`.
