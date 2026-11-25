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

Installing company-skills also installs and enables five plugins as dependencies:

- the Trail of Bits `differential-review` and `insecure-defaults` plugins (see [Bundled Trail of Bits plugins](#bundled-trail-of-bits-plugins-and-plugin-dev))
- the `python-pro`, `rust-engineer`, and `typescript-pro` language skills (see [Bundled language practice skills](#bundled-language-practice-skills))

Go practice and review come from company-skills' own `golang-practices` and `golang-review` skills.

Inside a session, `/plugin marketplace add cipherstash/skills` and `/plugin install company-skills@company` do the same. Start a new session, then invoke a skill by its namespaced name, for example `/company-skills:review-fix`.

To update to the latest published skills, refresh the marketplace, update the plugin, then start a new session:

```sh
claude plugin marketplace update company
claude plugin update company-skills@company
```

Updating from a release before 0.15.0 leaves the removed `golang-pro` plugin installed but failing to load. Uninstall it as described in [Bundled language practice skills](#bundled-language-practice-skills).

Updating company-skills does not update its dependencies. When a release moves the pinned commit of a bundled plugin, update that plugin by name as well:

```sh
claude plugin update differential-review@company
claude plugin update insecure-defaults@company
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

Codex does not install plugin dependencies, so add the two Trail of Bits plugins explicitly (see [Bundled Trail of Bits plugins](#bundled-trail-of-bits-plugins-and-plugin-dev)). The command syntax was checked against `codex-cli 0.169.0`. Start a fresh session and use `/skills` or type `$` to select an installed skill, then supply its inputs. Skills can also match requests automatically.

If your CLI does not provide `plugin add`, restart the desktop app, choose **Company** in the Plugins Directory, and install **Company Skills** there. See [OpenAI’s plugin packaging guide](https://developers.openai.com/plugins/build/plugins) for marketplace configuration.

To update, refresh the marketplace, then reinstall the plugin:

```sh
codex plugin marketplace upgrade company
codex plugin remove company-skills@company
codex plugin add company-skills@company
```

## Bundled Trail of Bits plugins and plugin-dev

The `company` marketplace also lists three plugins from [Trail of Bits' skills repository](https://github.com/trailofbits/skills), so accounts and routines that cannot add the Trail of Bits marketplace still get them:

| Plugin | Provides |
| --- | --- |
| `differential-review` | The `differential-review` skill, the `/differential-review:diff-review` command, and the `adversarial-modeler` agent: a security-focused review of a PR, commit, or diff |
| `insecure-defaults` | The `/insecure-defaults:audit` command and its `audit-pipeline` workflow: an audit for fallback secrets, default credentials, fail-open switches, weak crypto, permissive access, and debug leakage |
| `code-improver` | The `skill-improver`, `code-improver`, and `pr-improver` skills: a review-and-fix loop that runs until a review comes back clean. Claude Code only, because it runs as a workflow |

`skill-improver` reviews with the `plugin-dev:skill-reviewer` agent, so the Claude catalog also lists Anthropic's `plugin-dev` plugin from [claude-plugins-official](https://github.com/anthropics/claude-plugins-official), pinned to one full upstream commit SHA and published under the Apache 2.0 licence.

The Trail of Bits entries are `git-subdir` sources pinned to one full upstream commit SHA. No upstream files are copied into this repository. They are published by Trail of Bits under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), not this repository's MIT licence.

- **Claude Code:** company-skills declares `differential-review` and `insecure-defaults` as dependencies, so `claude plugin install company-skills@company` installs and enables them. Checked with Claude Code 2.1.327.
- **Claude Code, opt-in:** `code-improver` and `plugin-dev` are not dependencies, because `plugin-dev` adds a whole plugin-development toolkit to every session. Install them by name when you want `skill-improver`, and skip `plugin-dev@company` if you already have `plugin-dev` from `claude-plugins-official`. Checked with Claude Code 2.1.330.

  ```sh
  claude plugin install code-improver@company
  claude plugin install plugin-dev@company
  ```

  Then run `/code-improver:skill-improver <skill name or path>`.
- **Codex:** the Codex catalog lists only `differential-review` and `insecure-defaults`. Both install from the same pinned entries, but Codex has no plugin dependencies, so install each with `codex plugin add` as shown under [Codex](#codex). `insecure-defaults` ships a Claude Code command and workflow and no `skills/` directory, so it may expose nothing in Codex. Checked with `codex-cli 0.169.0`. `code-improver` and `plugin-dev` are Claude-catalog-only and were not tested in Codex.

Nothing auto-updates them: a plugin with a pinned `sha` stays on that commit through marketplace refreshes and plugin updates. To move the Trail of Bits pin, open a pull request that:

1. Reviews the upstream changes to `plugins/differential-review`, `plugins/insecure-defaults`, and `plugins/code-improver` since the current SHA, and checks that `skill-improver` still names the `plugin-dev:skill-reviewer` agent.
2. Changes `sha` to the same new full 40-character commit SHA for all three Trail of Bits entries in `.claude-plugin/marketplace.json`, and for the two in `.agents/plugins/marketplace.json`. The validator fails when a pin differs between the two catalogs or a SHA is not a full commit. It does not check `code-improver`, which only the Claude catalog lists, so move that one by hand.
3. Bumps the plugin version in all three manifests, as described in [Releases](CONTRIBUTING.md#releases).

To move the `plugin-dev` pin, review the upstream changes to `plugins/plugin-dev` in `anthropics/claude-plugins-official` since its SHA, confirm the `skill-reviewer` agent is still there, change its `sha` in `.claude-plugin/marketplace.json`, and bump the version as above.

Installed users get a moved pin only when they update that plugin by name, for example `claude plugin update code-improver@company` and `claude plugin update plugin-dev@company`.

## Bundled language practice skills

The `company` marketplace also lists three language skills from [Jeffallan's claude-skills repository](https://github.com/Jeffallan/claude-skills), each as its own plugin:

| Plugin | Provides |
| --- | --- |
| `python-pro` | The `python-pro` skill, with references on async patterns, packaging, the standard library, testing, and the type system |
| `rust-engineer` | The `rust-engineer` skill, with references on async, error handling, ownership, testing, and traits |
| `typescript-pro` | The `typescript-pro` skill, with references on advanced types, configuration, patterns, type guards, and utility types |

They are reference material on language practice. Upstream wrote them for writing code, not reviewing it, so their descriptions also match requests to write Python, Rust, or TypeScript.

Upstream publishes all 67 of its skills as one plugin. Each entry here installs one skill instead: a `git-subdir` source pointing at that skill's directory, `skills/<name>`, with `"strict": false` and `"skills": ["./"]` so the directory loads as a plugin holding a single skill. All three are pinned to the commit of the upstream v0.4.20 release. No upstream files are copied into this repository. They are published by Jeffallan under the MIT licence.

- **Claude Code:** company-skills declares all three as dependencies, so `claude plugin install company-skills@company` installs and enables them. Invoke one by its namespaced name, for example `/python-pro:python-pro`. Checked with Claude Code 2.1.328.
- **Codex:** the Codex catalog does not list them, and they have not been tested there.

Nothing auto-updates them. To move the pin, open a pull request that:

1. Reviews the upstream changes to the three skill directories since the current SHA.
2. Changes `sha` for all three entries in `.claude-plugin/marketplace.json` to the same new full 40-character commit SHA.
3. Bumps the plugin version in all three manifests, as described in [Releases](CONTRIBUTING.md#releases).

Installed users receive the new commit only when they update each of the three plugins by name, as shown under [Claude Code](#claude-code).

0.15.0 removes the bundled `golang-pro` plugin. company-skills' `golang-practices` and `golang-review` replace it. Updating an install from an earlier release leaves `golang-pro` installed. It no longer loads, because the marketplace no longer lists it: `claude plugin list` reports it as failed to load, with `Plugin golang-pro not found in marketplace company`. While it is installed, `claude plugin prune` removes nothing and reports `cannot determine orphans`. Uninstall it by name:

```sh
claude plugin uninstall golang-pro@company
```

`claude plugin prune` works again once `golang-pro` is gone. It removes any other auto-installed dependency that nothing needs. Add `--dry-run` to list them first. Checked with Claude Code 2.1.329 by updating 0.13.0 to a pre-release build of this release, made before it was renumbered from 0.14.0 to 0.15.0.

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
| `review-audit` | Audit existing PR feedback against the PR head | Explicit or automatic |
| `review-cross-check` | Verify new findings and report which are new against existing PR feedback; reports only, so run `review-post` to publish them | Explicit or automatic |
| `review-post` | Post review findings to a PR with source-tagged inline comments and a review attestation | Explicit or automatic |
| `review-fix` | Verify findings and fix confirmed defects | Explicit or automatic |
| `run-report` | Log every problem an unattended run hits and publish a run report as a Claude artifact | Explicit or automatic |
| `vanta-triage` | Reconcile open Vanta vulnerability findings with Linear issues: file, retarget, refresh, realign, reopen, and close | Explicit or automatic |
| `vanta-remediate` | Build the Remediate queue from Todo Vanta Linear issues, patch dependencies, verify every lockfile, and open PRs | Explicit or automatic |
| `rust-sdk-dx` | Conventions for public Rust APIs in libraries and SDKs | Automatic while writing Rust library code |
| `rust-security` | Rules for Rust code that handles secrets, cryptography, and authentication | Automatic while writing Rust that touches secrets |
| `rust-testing` | Conventions for Rust tests: nextest, scenario modules, fake data, mocktail, paused time | Automatic while writing Rust tests |
| `golang-practices` | Conventions for writing Go: errors, concurrency, naming, interfaces, generics, testing, project structure, security, performance, dependencies and embedding wazero, with examples that compile and pass the race detector | Automatic while writing Go |
| `golang-review` | Review a Go change against a ten-area checklist, from error handling and concurrency to security, dependencies and breaking changes, with `go vet`, race-enabled tests with coverage, `gofmt`, `go mod tidy -diff` and an exported-API comparison as evidence, ending in a verdict | Explicit or automatic |
| `filing-github-issues` | Draft and file well-structured GitHub issues on CipherStash repos | Explicit or automatic |
| `authoring-pull-requests` | Branch, commit, and open draft pull requests with a consistent structure | Explicit or automatic |
| `plain-language` | Write, rewrite, and review prose in plain language (ISO 24495 and GOV.UK), with a bundled checker | Explicit or automatic |

Code review skills (`review-*`) work with the findings of a code review: auditing a PR's existing feedback, cross-checking new findings against it, posting them, and fixing them. None of them performs the review itself. `golang-review` performs one for a Go change and reports findings in the severities they take.

Convention skills (`rust-*` and `golang-practices`) carry coding rules rather than a workflow. Claude Code applies them automatically and hides them from the `/` menu; Codex selects them implicitly.

`review-audit` and `review-cross-check` require Python 3, Git, and `gh` authenticated for the target repository; `review-post` requires `gh` and `python3` or `jq`. `golang-review` requires Git and the Go toolchain to run its checks, and the GitHub MCP server or `gh` to review a pull request; without them it reviews by reading and reports the checks it could not run. When `golangci-lint` or `govulncheck` is not installed, it fetches it from the Go module proxy at the version `golang-practices` pins. These are local CLI dependencies; the plugin does not bundle an MCP server.

The Vanta skills also need the Linear connector, read-only Vanta API credentials (`vanta-api.all:read`) with network access to `api.vanta.com` for `vanta-triage`, either as an environment network secret of type OAuth 2.0 client credentials for `api.vanta.com` or as `VANTA_CLIENT_ID` and `VANTA_CLIENT_SECRET`, and each target ecosystem's toolchain (`cargo`, `pnpm`/`npm`/`yarn`/`bun`, `go`, `poetry`/`uv`) for `vanta-remediate`. `vanta-remediate` also needs the GitHub MCP server for pull requests and `git` push access to the target repos; it does not use the `gh` CLI. Both run unattended, so they suit Claude Code routines.

`plain-language` is ported from [auxesis/plain-language-skill](https://github.com/auxesis/plain-language-skill) under the Apache License 2.0; its `LICENSE` and `NOTICE` files carry the licence, the Open Government Licence credit for the GOV.UK material, and the changes made here. The port ships the skill and its checker, `scripts/check.py`, which needs Python 3.9 or later and no packages. It does not ship the upstream plugin's hooks, which add the rules to every session and send back chat replies that break them; install that plugin separately if you want them.

`run-report` publishes through Claude's Artifact tool; on a host without it, the report goes in the run's final message. List it first in a routine's prompt so it logs problems from the start of the run, for example:

```text
/company-skills:run-report Code review
/code-review medium
/company-skills:review-cross-check
/company-skills:review-post
```

## Renamed skills

The code review skills were renamed in 0.8.0 and their deprecated aliases were removed in 0.10.0. This table is kept permanently so an old name always points to its replacement.

| Old name | New name | Notes |
| --- | --- | --- |
| `address-code-review` | `review-fix` | |
| `audit-pr-feedback` | `review-audit` | |
| `cross-check-review-findings` | `review-cross-check` | Ends at a report; run `review-post` to publish the findings |

## Contribute

Follow [CONTRIBUTING.md](CONTRIBUTING.md) to add or change a skill: naming, progressive disclosure, required behavior cases, releases, and the validation commands to run. Pull requests run `python3 scripts/validate.py`, `python3 -m unittest discover -s scripts/tests`, and each skill's `tests/` suite in GitHub Actions; the `claude plugin validate --strict` checks run locally only.

The `golang-practices` script tests check that every Go block in the skill's references is quoted from a file in its examples module. They also run each benchmark in that module once. A separate job runs the Go check suite, listed in [`references/checks.md`](plugins/company-skills/skills/golang-practices/references/checks.md), over the module.

The `golang-review` script tests check the skill's seeded-defect fixture, a sample change with at least one planted defect in each of the ten checklist areas. They check that every expected finding quotes the line it names, and that the base vets and passes with the race detector. They also reproduce each planted defect that a tool or a short probe can show, such as the race and a panic on empty input. Without Go, the Go checks in both skills' script tests are skipped locally with a message, and they fail in CI.

See the official [Codex skills documentation](https://developers.openai.com/codex/skills/) and [Claude Code plugin marketplace documentation](https://code.claude.com/docs/en/plugin-marketplaces) for current publishing and installation options.

## License

The repository is licensed under the MIT License; see [LICENSE](LICENSE).

`plugins/company-skills/skills/plain-language` is licensed under the Apache License 2.0, and some of its content is public sector information under the Open Government Licence v3.0. See its [LICENSE](plugins/company-skills/skills/plain-language/LICENSE) and [NOTICE](plugins/company-skills/skills/plain-language/NOTICE). `plugins/company-skills/skills/golang-practices` adapts MIT-licensed material from [Jeffallan/claude-skills](https://github.com/Jeffallan/claude-skills); see its [LICENSE](plugins/company-skills/skills/golang-practices/LICENSE) and [NOTICE](plugins/company-skills/skills/golang-practices/NOTICE). The plugin manifests declare the combined SPDX expression `MIT AND Apache-2.0 AND OGL-UK-3.0`.
