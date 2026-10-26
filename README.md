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

Inside a session, `/plugin marketplace add cipherstash/skills` and `/plugin install company-skills@company` do the same. Start a new session, then invoke a skill by its namespaced name, for example `/company-skills:address-code-review`.

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

The command syntax was checked against `codex-cli 0.160.0`. Start a fresh session and use `/skills` or type `$` to select an installed skill, then supply its inputs. `address-code-review` requires explicit selection; the PR feedback skills can also match requests automatically.

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
| `address-code-review` | Verify findings and fix confirmed defects | Explicit only |
| `audit-pr-feedback` | Audit existing PR feedback against the PR head | Explicit or automatic |
| `cross-check-review-findings` | Compare new findings with existing PR feedback and draft a response | Explicit or automatic |
| `vanta-triage` | Reconcile open Vanta vulnerability findings with Linear issues: file, retarget, and close | Explicit or automatic |
| `vanta-remediate` | Patch dependencies for Vanta Linear issues, verify every lockfile, and open PRs | Explicit or automatic |
| `rust-sdk-dx` | Conventions for public Rust APIs in libraries and SDKs | Automatic while writing Rust library code |
| `rust-security` | Rules for Rust code that handles secrets, cryptography, and authentication | Automatic while writing Rust that touches secrets |
| `rust-testing` | Conventions for Rust tests: nextest, scenario modules, fake data, mocktail, paused time | Automatic while writing Rust tests |
| `filing-github-issues` | Draft and file well-structured GitHub issues on CipherStash repos | Explicit or automatic |
| `authoring-pull-requests` | Branch, commit, and open draft pull requests with a consistent structure | Explicit or automatic |
| `vitaminc` | Use the vitaminc crates for secrets, randomness, encryption, key wrapping, and keyed hashes | Automatic while writing Rust that touches secrets |

Rust convention skills (`rust-*`) carry coding rules rather than a workflow. Claude Code applies them automatically and hides them from the `/` menu; Codex selects them implicitly.

The `vitaminc` skill is a copy of `.claude/skills/vitaminc` in [cipherstash/vitaminc](https://github.com/cipherstash/vitaminc), where every Rust block is doctested against the crates. Change it there, then copy it here unchanged. `rust-security` holds the company rules and defers vitaminc's API to this skill.

The PR feedback skills require Python 3, Git, and `gh` authenticated for the target repository. These are local CLI dependencies; the plugin does not bundle an MCP server.

The Vanta skills also need the Linear connector, read-only Vanta API credentials (`vanta-api.all:read`) with network access to `api.vanta.com` for `vanta-triage`, either as an environment network secret of type OAuth 2.0 client credentials for `api.vanta.com` or as `VANTA_CLIENT_ID` and `VANTA_CLIENT_SECRET`, and each target ecosystem's toolchain (`cargo`, `pnpm`/`npm`/`yarn`/`bun`, `go`, `poetry`/`uv`) for `vanta-remediate`. `vanta-remediate` also needs the GitHub MCP server for pull requests and `git` push access to the target repos; it does not use the `gh` CLI. Both run unattended, so they suit Claude Code routines.

## Contribute

Follow [CONTRIBUTING.md](CONTRIBUTING.md) to add or change a skill: naming, progressive disclosure, required behavior cases, releases, and the validation commands to run. Pull requests run `python3 scripts/validate.py`, `python3 -m unittest discover -s scripts/tests`, and each skill's `tests/` suite in GitHub Actions; the `claude plugin validate --strict` checks run locally only.

See the official [Codex skills documentation](https://developers.openai.com/codex/skills/) and [Claude Code plugin marketplace documentation](https://code.claude.com/docs/en/plugin-marketplaces) for current publishing and installation options.

## License

MIT
