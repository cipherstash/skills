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

Inside a session, `/plugin marketplace add cipherstash/skills` and `/plugin install company-skills@company` do the same. Start a new session, then invoke a skill by its namespaced name, for example `/company-skills:review-fix`.

To update to the latest published skills, refresh the marketplace, update the plugin, then start a new session:

```sh
claude plugin marketplace update company
claude plugin update company-skills@company
```

### Codex

```sh
codex plugin marketplace add cipherstash/skills --ref main
codex plugin add company-skills@company
codex plugin list --marketplace company
```

The command syntax was checked against `codex-cli 0.160.0`. Start a fresh session and use `/skills` or type `$` to select an installed skill, then supply its inputs. Skills can also match requests automatically.

If your CLI does not provide `plugin add`, restart the desktop app, choose **Company** in the Plugins Directory, and install **Company Skills** there. See [OpenAI’s plugin packaging guide](https://developers.openai.com/plugins/build/plugins) for marketplace configuration.

To update, refresh the marketplace, then reinstall the plugin:

```sh
codex plugin marketplace upgrade company
codex plugin remove company-skills@company
codex plugin add company-skills@company
```

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
| `code-review` | Review a PR or diff through selected specialist agents, then hand findings to cross-check and posting | Explicit or automatic |
| `review-test-gaps` | Find missing regression protection and ineffective test assertions | Selected by code-review, or focused request |
| `review-infracode` | Review infrastructure lifecycle, permissions, deployment, CI, and observability risks | Selected by code-review, or focused request |
| `review-golang` | Review Go semantics, concurrency, errors, and API compatibility | Selected by code-review, or focused request |
| `review-typescript` | Review TypeScript/JavaScript boundaries, types, async behavior, and compatibility | Selected by code-review, or focused request |
| `review-rust` | Review Rust safety, async behavior, APIs, and applicable company conventions | Selected by code-review, or focused request |
| `review-python` | Review Python state, exceptions, async behavior, packaging, and test validity | Selected by code-review, or focused request |
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
| `filing-github-issues` | Draft and file well-structured GitHub issues on CipherStash repos | Explicit or automatic |
| `authoring-pull-requests` | Branch, commit, and open draft pull requests with a consistent structure | Explicit or automatic |

Start a fresh review with `code-review`. It pins the diff or working snapshot, selects the applicable lower-level review skills, delegates them through the host's agents, and combines supported findings with their evidence and sources. Hosts without subagents use the same skills sequentially. No separate agent setup, model matrix, or external review runner is needed.

In Claude Code, use `/company-skills:code-review <PR URL or comparison>`. In Codex, select the installed `company-skills` `code-review` skill from `/skills` or the `$` picker and provide the target. Prefer the plugin-qualified selection if a personal skill also uses the name `code-review`.

For PRs, `code-review` passes findings to `review-cross-check` unless raw review alone was requested. `review-post` publishes the resulting postable set when asked. Receiving agents use `review-audit` to check existing feedback against the current head and `review-fix` to verify and fix outstanding findings. A review request alone does not post or fix anything. Local dirty reviews remain identified as snapshots until verified against a PR head.

The six specialist capabilities are independently authored adaptations informed by an [audit of auxesis/junk pr-review](plugins/company-skills/skills/code-review/references/upstream-audit.md). The audit records the pinned source, omitted infrastructure, and corrected source assumptions.

Rust convention skills (`rust-*`) carry coding rules rather than a workflow. Claude Code applies them automatically and hides them from the `/` menu; Codex selects them implicitly.

`review-audit` and `review-cross-check` require Python 3, Git, and `gh` authenticated for the target repository; `review-post` requires `gh` and `python3` or `jq`. These are local CLI dependencies; the plugin does not bundle an MCP server.

The Vanta skills also need the Linear connector, read-only Vanta API credentials (`vanta-api.all:read`) with network access to `api.vanta.com` for `vanta-triage`, either as an environment network secret of type OAuth 2.0 client credentials for `api.vanta.com` or as `VANTA_CLIENT_ID` and `VANTA_CLIENT_SECRET`, and each target ecosystem's toolchain (`cargo`, `pnpm`/`npm`/`yarn`/`bun`, `go`, `poetry`/`uv`) for `vanta-remediate`. `vanta-remediate` also needs the GitHub MCP server for pull requests and `git` push access to the target repos; it does not use the `gh` CLI. Both run unattended, so they suit Claude Code routines.

`run-report` publishes through Claude's Artifact tool; on a host without it, the report goes in the run's final message. List it first in a routine's prompt so it logs problems from the start of the run, for example:

```text
/company-skills:run-report Code review
/company-skills:code-review <PR URL>
/company-skills:review-cross-check
/company-skills:review-post
```

### Removed aliases

0.10.0 removes the explicit-only aliases left by the 0.8.0 rename of the code review skills. Invoke the new names instead: `review-fix` for `address-code-review`, `review-audit` for `audit-pr-feedback`, and `review-cross-check` for `cross-check-review-findings`. `review-cross-check` ends at a report; `review-post` publishes the findings.

## Contribute

Follow [CONTRIBUTING.md](CONTRIBUTING.md) to add or change a skill: naming, progressive disclosure, required behavior cases, releases, and the validation commands to run. Pull requests run `python3 scripts/validate.py`, `python3 -m unittest discover -s scripts/tests`, and each skill's `tests/` suite in GitHub Actions; the `claude plugin validate --strict` checks run locally only.

See the official [Codex skills documentation](https://developers.openai.com/codex/skills/) and [Claude Code plugin marketplace documentation](https://code.claude.com/docs/en/plugin-marketplaces) for current publishing and installation options.

## License

MIT
