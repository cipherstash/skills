---
name: vanta-remediate
description: Patch the dependency vulnerabilities tracked by Vanta Linear issues — for each "[Vanta] Remediate {package} to {version} ({repo})" issue, find every lockfile location that resolves a vulnerable version, bump it with the right package manager, verify the fix landed, open a GitHub PR, and move the Linear issue to In Review. Also assesses "[Vanta] Assess" container OS-package issues on request. Use when asked to fix, patch, remediate, or open PRs for Vanta or Dependabot findings, work a CIP issue from the AppSec project, or run the scheduled Vanta remediation, including unattended routine runs. Does not query Vanta or file issues (vanta-triage does that).
argument-hint: "[CIP-XXXX ...] [dry run]"
---

# vanta-remediate

Turn Todo Vanta issues in Linear into verified pull requests. A patch counts only when [scripts/deps.py](scripts/deps.py) shows that no lockfile in the repository still resolves a vulnerable version. The package manager exiting 0 is not enough: a transitive pin or a second lockfile routinely survives a bump.

The run is unattended-safe: it never asks a question mid-run. When a decision belongs to a human, it leaves the evidence on the Linear issue and moves on.

## Inputs

- **Issues**: one or more `CIP-XXXX` ids. A request that names a repo, package, and fix version directly is worked the same way. First look for a matching open `[Vanta] Remediate` issue and use it if found. Otherwise skip every Linear step, and name the branch `fix/vanta-<package slug>`, never a bare `fix/<package>` a human may already use. With no issue there is no advisory block: the one fix check is `--ecosystem <eco> --package <pkg> --target <version> …`, there is no residual check, and the report says the advisories were not checked.
  - With neither, take Todo issues in the configured project whose titles start `[Vanta] Remediate`, highest priority first, then earliest due date. Keep taking issues until 5 end in **PR opened**, **existing PR linked**, or **already fixed**, or 15 have been examined. Skipped and blocked issues don't count toward the 5, so a few stuck issues cannot starve the queue.
  - With a request to "include assessments", also take Todo `[Vanta] Assess` issues.
- **Mode**: apply by default. A dry run patches and verifies in a worktree but does not push, open PRs, or write to Linear. It keeps the worktree for inspection only when it holds a diff, and later runs on that issue are blocked until a human removes it.
- **Configuration**: the Linear team, project and assignee, and the image-to-repo map, are in vanta-triage's `references/config.json`: team **Product Engineering**, project **AppSec (ongoing)**, GitHub org **cipherstash**. Repos are looked up locally under `$VANTA_REPOS_BASE` (default `~/src`) before cloning.

Needs `git` with push access to the target repos, Python 3, the target ecosystem's toolchain (`cargo`, `pnpm`/`npm`/`yarn`/`bun`, `go`, `poetry`/`uv`), the GitHub MCP server's tools (`list_pull_requests`, `create_pull_request`, `update_pull_request`), and the Linear connector's tools. Use the GitHub MCP tools for every GitHub API step, never the `gh` CLI: Claude Code routines block `gh pr create`, and the tools work on every host that has the server.

## Scripts

Resolve each script from this skill's directory. All four are Python 3.9+, standard library only (workspace.py also calls `git`), and each docstring is the full contract. Save every JSON output under `<scratch>`.

- **[scripts/checks.py](scripts/checks.py)** `--issue <file>` reads a saved `get_issue` result and prints the exact deps.py checks for it. It prints `{status, reasons, repo, ecosystem, package, targets, advisories, fix_checks, residual_check, unfixed_advisories, …}`. It exits 0 for `ok`, 1 for `skip` (`reasons` says why), and 2 on bad usage or an unreadable file.
  - It reads only the fenced `json` advisory block in triage's generated section, never the Markdown table. It trusts the block only when the block's recomputed digest matches the section's `Advisory set:` line and its key matches the `Vanta key:` line. Anything else is a skip that says "needs a triage refresh".
  - It keeps every advisory in a check. A fixed advisory with no range, or a title whose targets differ from the block's, adds a `--target`-only fix check beside the range check. A differing title also adds a `--target`-only check on the block's targets, so a hand-edited title can never lower the fix version. An advisory with no fix always goes into the residual check, with a range matching every version when Vanta gave none, and its id into `unfixed_advisories`.

- **[scripts/deps.py](scripts/deps.py)** `<dir> --ecosystem <eco> --package <pkg> --target <v> … --affected "<range>" …` prints the resolved versions as JSON. Exit 0: every lockfile was read in full and nothing resolved is vulnerable, including when the package is absent. Exit 1: a resolved version is vulnerable (`vulnerable` lists each lockfile and version). Exit 2: bad usage, or a lockfile or entry that could not be read, including the scanned package locked without a resolved version; `unsupported` names it.
- **[scripts/gate.py](scripts/gate.py)** is the evidence gate. It reads deps.py's JSON and exit codes (or, for a container claim, a determinations file checked against checks.py's output), and decides whether they support a claim on the ref they came from. It prints `{pass, outcome, reasons, notes, must_name_unfixed}` and exits 0 on a pass, 1 on a failure, and 2 on bad usage. A missing or unreadable input fails the gate; it never passes. It fails on any `unsupported` entry, because an unattended run cannot check a file by hand. **No issue moves to Done or In Review, and no PR is linked or opened, without a passing gate result for that claim.** When `must_name_unfixed` is non-empty, the PR body and the Linear comment name each advisory in it.
- **[scripts/workspace.py](scripts/workspace.py)** decides where a worktree may start, and creates or removes only worktrees this run owns. Inspection never changes anything. It prints `{action, base, pr, reasons, evidence}` and exits 0 for `create` or `resume`, 1 for `blocked`, and 2 on bad usage or a git failure.
  - `--create` makes the worktree and writes an ownership marker, `vanta-remediate-owner`, holding this run's id, into that worktree's git directory. The marker sits outside the working tree, so it never shows in a diff.
  - `--cleanup` removes a worktree only when its marker holds this run's id, and deletes the local branch only when it is not on origin and holds nothing beyond the default branch. It refuses anything else and deletes nothing.
  - Ownership is therefore checked, never assumed: a leftover worktree from a dry run, an interrupted run, or a human always blocks.

At the start of the run, make a run id (`python3 -c 'import uuid; print(uuid.uuid4())'`) and pass it as `--run-id` to every `--create` and `--cleanup` call.

## Per issue

Process issues one at a time. Each issue ends in exactly one outcome: **PR opened**, **existing PR linked**, **already fixed**, **blocked**, or **skipped**. Record it with the evidence. A deps.py measurement means: run `deps.py <dir> <args>` for each list in checks.py's `fix_checks`, and for `residual_check` when it is not null. Save each stdout to its own file and keep each exit code. Pass every fix check to gate.py as its own `--fix <file> --fix-exit <code>` pair. Pass the residual check as `--residual <file> --residual-exit <code>`, and each `unfixed_advisories` id as `--unfixed-advisory <id>`. Leave no check out: gate.py passes only when every fix check exits 0.

1. **Read the issue.** Call `get_issue` with `description`, `status`, and `attachments`, save the result to `<scratch>/<id>.json` as returned, and run `checks.py --issue <scratch>/<id>.json > <scratch>/<id>-checks.json`.
   - **`skip`** is the outcome **skipped**, with checks.py's `reasons` in the report. This covers:
     - an issue with no advisory block, or a block that fails its integrity check. Triage refreshes the issue on its next run; never read the table or the title instead.
     - an issue with no GitHub repo (an asset name is not a repo: never clone or search for it).
     - a title that is not a Remediate title.
   - **`[Vanta] Assess` issues** whose block passes the integrity check come back as `skip` with their `images`, `repo`, and `advisories` filled in. Vanta often reports no fix, and deps.py does not read OS packages. Find and fetch the clone as in step 2, and make the worktree as in step 4. Then follow [references/containers.md](references/containers.md) in place of step 2's measurement and steps 3, 5, and 6. Its PR goes through step 7, which moves the issue to In Review only on the gate's `pr-in-review` outcome. An Assess issue whose source repo is unknown, both in the block's `repo` and in the config's `images` map, is **skipped**.
   - **`ok`**: take the repo, ecosystem, package, and targets from checks.py's output. It spells the package as Vanta does (Go module paths are case-sensitive). Its `fix_checks`, `residual_check`, and `unfixed_advisories` are every measurement below. checks.py applies the stale-title, no-fix, and missing-range rules itself; never add, drop, or edit a check.
   - **In Review.** An In Review issue with an open PR attached is in flight: skip it, unless its `Advisory set:` value differs from the one in this skill's last In Review comment. Triage refreshes a description without moving its state. In that case, measure the PR as in step 3, comment the gate result, and move the issue to Todo if the gate fails.

2. **Measure the default branch.**
   - Find a clone: `$VANTA_REPOS_BASE/<repo name>` whose `origin` is the repo, else `git clone https://github.com/<owner/repo>.git <scratch>/<repo name>`. Never patch the user's checkout or its branches.
   - Run `git -C <clone> fetch origin`, and read the default branch from `git -C <clone> ls-remote --symref origin HEAD` (the `ref: refs/heads/<default>` line).
   - Create a measurement worktree: `workspace.py --clone <clone> --path <fresh scratch path> --detach origin/<default> --create --run-id <id>`. Measure in it, then `--cleanup` it.
   - Run `gate.py --claim already-fixed --ref-kind default` with every check from that measurement.
     - `already-fixed`: mark the issue **Done** with a comment carrying the deps.py summaries, the commit sha (`git -C <clone> rev-parse origin/<default>`), and the `Advisory set:` value. Vanta clears it on its next scan, and vanta-triage reports it as awaiting rescan until then. Outcome **already fixed**.
     - `patch`: the default branch is still vulnerable; continue.
     - `blocked`: comment the gate's `reasons` and the deps.py summaries. Typical causes: only unfixed advisories remain, or a file could not be read. Outcome **blocked**.

3. **Check for a PR already in flight.**
   - Call `list_pull_requests` with `state: "open"`, `perPage: 100`, and `fields: ["number", "title", "head", "base", "user"]`, raising `page` until a page returns fewer than 100. Candidates are PRs, from Dependabot or a person, whose title or head branch names the package. A PR into any branch other than the default is never a candidate.
   - A title alone proves nothing: Dependabot often bumps one `package.json` without touching the lockfile. Measure each candidate:
     - Run `git -C <clone> fetch origin pull/<n>/merge`, the result of merging it, and use `--ref-kind merge`.
     - When GitHub has no merge ref (a conflict), fetch `pull/<n>/head` instead and use `--ref-kind head`. The gate's note says the comment must mention this.
     - Measure in a `--detach FETCH_HEAD` worktree, as in step 2.
   - Run `gate.py --claim linked --ref-kind <merge|head> --pr-base <base> --default-branch <default>` with every check from that measurement. For this skill's own branch, also pass `--diff-files` (step 6's list).
   - On `linked`: `save_issue` with `links: [{url, title: "GitHub PR"}]` and `state: "In Review"`, plus a comment carrying the deps.py summaries, the ref and its sha, any `must_name_unfixed` advisories, and the `Advisory set:` value. Outcome **existing PR linked**.
   - On `not-linked`: note the PR and the gate's reasons in the report and in this skill's PR body. A PR whose head is this issue's branch is resumed in step 4 and updated in step 7, never duplicated.

4. **Worktree.** The branch is `fix/<id lowercased>-<package slug>`. The package slug is the package name with `@` dropped and `/` turned into `-`. The path is `<clone>-<id lowercased>` for a local clone, or a scratch path otherwise.
   - Save the PRs for that head: call `list_pull_requests` with `state: "all"`, `head: "<owner>:<branch>"`, and `fields: ["number", "state", "merged_at"]`, and write the PRs to `<scratch>/prs.json` as a JSON list of `{number, state, merged_at}`.
   - Run `workspace.py --clone <clone> --path <path> --branch <branch> --default <default> --pr-json <scratch>/prs.json --create --run-id <id>`.
     - `blocked`: the outcome is **blocked**. Report its `reasons` and `evidence` (the leftover's status, including ignored files, or the commits that would be lost), and delete nothing. Never work around it with `git worktree add -B`, `worktree remove`, or `branch -D`: `-B` silently resets a branch holding commits.
     - `resume`: a previous run pushed `<branch>`. The worktree starts from `origin/<branch>`, which may already carry the patch, and may hold a human's later commits, which are kept. When `pr` is set, that open PR is this issue's PR: update it in step 7.
     - `create`: the worktree starts from `origin/<default>`.
   - **Every outcome from here on ends with `workspace.py --clone <clone> --path <path> --cleanup --run-id <id>`.** The exceptions are a dry run that left a diff, and a refused cleanup, which goes in the report.

5. **Patch.** Follow [references/ecosystems.md](references/ecosystems.md) for the ecosystem. It escalates from an in-range update, to a manifest bump, to an override, and says when to stop. Fix every lockfile deps.py listed, not only the root one. A resumed worktree whose fix checks already all exit 0 needs no patch.

6. **Verify.**
   - Run the ecosystem's lockfile consistency check from ecosystems.md. CI runs the test suites, so don't run them locally.
   - Commit any changes in the worktree; a resumed branch that already passes has none. The commit message is `fix(deps): patch <package> to <landed version(s)>`. Leave out the Linear id: some repos are open source, and the branch name already carries the id, which Linear's GitHub integration links on.
   - `git -C <path> status --porcelain` must print nothing, so what is measured is what will be pushed.
   - Measure the worktree. List the branch's changes with `git -C <path> diff --name-only $(git -C <path> merge-base origin/<default> HEAD) HEAD`, which covers commits a human pushed as well as this run's.
   - Run `gate.py --claim opened --ref-kind fix-branch --diff-files <those files>` with every check from that measurement. Only manifests, lockfiles, and requirements or constraints files (the dependency files deps.py reads) may change.
   - On a failure, the outcome is **blocked**.
     - Comment the gate's reasons and the deps.py output.
     - When the target was not reached, also comment what pins the old version (the dependents chain from `cargo tree -i`, `pnpm why`, `npm explain`, or `go mod why`) and the smallest change that would unblock it.
     - A scope failure means the toolchain or a human changed other files: leave the branch for a human.

7. **Push and open or update the PR** (skip in dry-run mode).
   - Push with `git -C <path> push -u origin <branch>`, never forced. A rejected push is **blocked**: someone pushed meanwhile.
   - PR body: each advisory (id, link, severity), each lockfile's version before and after, the verification run, and every advisory in `must_name_unfixed`, marked as still unfixed. Write it to `<scratch>/pr-body.md`.
   - When step 4 returned a `pr`, update that PR in place with `update_pull_request` (`pullNumber: <pr>`, `body`: the file's contents). Otherwise open one with `create_pull_request`: `title: "fix(deps): patch <package> to <version>"`, `head: <branch>`, `base: <default>`, `body`: the file's contents, and `draft: true` or `false`.

   - Draft when the patch changed a direct dependency's major line (0.x minor counts as major), and say why in the body.
   - Linear:
     - `save_issue` with `links: [{url: <PR url>, title: "GitHub PR"}]` and `state: "In Review"`. For an Assess issue, set In Review only on `pr-in-review`.
     - A comment summarising the before and after versions, the head sha, any `must_name_unfixed` advisories, the draft reason when the PR is a draft, and the `Advisory set:` value. Step 1's In Review check compares against that value.

   Outcome **PR opened**.

### Blocked outcomes

A blocked issue stays in, or moves back to, **Todo**. An In Review issue whose PR has merged, but whose residual check (an advisory with no fix) still matches on the default branch, goes back to Todo with the residual summary. Post a blocked comment only when its evidence differs from this skill's last comment on the issue, so scheduled runs don't repeat themselves. A blocked issue in a request with no Linear issue goes in the report only.

## Report

One line per issue: id, outcome, repo, package, versions before → after, the PR link or the reason. Then anything unsupported, blocked, or needing a human decision (draft major bumps, container determinations to file in Vanta, leftover worktrees and branches, refused cleanups). In dry-run mode, list each kept worktree path and its diff stat, and say plainly that nothing was pushed or written. Also say that each kept worktree must be removed (`git worktree remove --force <path>`) and its branch deleted (`git branch -D <branch>`), after saving anything committed there, before the issue can be applied.

## Boundaries

- Never force-push, rewrite a branch that has a PR with review activity, merge PRs, or push to a default branch.
- Never weaken a lockfile check (`--no-frozen-lockfile` in CI config) or delete a lockfile to regenerate it, to make a bump pass.
- Never remove a worktree or delete a branch except through `workspace.py --cleanup`.
- Close nothing on the strength of a PR alone; vanta-triage closes issues when Vanta stops reporting them. The one exception is step 2's already-fixed case, which rests on the default branch's lockfile evidence.
