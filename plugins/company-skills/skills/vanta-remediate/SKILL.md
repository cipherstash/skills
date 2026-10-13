---
name: vanta-remediate
description: Patch the dependency vulnerabilities tracked by Vanta Linear issues — for each "[Vanta] Remediate {package} to {version} ({repo})" issue, find every lockfile location that resolves a vulnerable version, bump it with the right package manager, verify the fix landed, open a GitHub PR, and move the Linear issue to In Review. Also assesses "[Vanta] Assess" container OS-package issues on request. Use when asked to fix, patch, remediate, or open PRs for Vanta or Dependabot findings, work a CIP issue from the AppSec project, or run the scheduled Vanta remediation, including unattended routine runs. Does not query Vanta or file issues (vanta-triage does that).
argument-hint: "[CIP-XXXX ...] [dry run]"
---

# vanta-remediate

Turn Todo Vanta issues in Linear into verified pull requests. A patch counts only when [scripts/deps.py](scripts/deps.py) shows that no lockfile in the repository still resolves a vulnerable version. The package manager exiting 0 is not enough: a transitive pin or a second lockfile routinely survives a bump.

The run is unattended-safe: it never asks a question mid-run. When a decision belongs to a human, it leaves the evidence on the Linear issue and moves on.

## Inputs

- **Issues**: one or more `CIP-XXXX` ids. A request that names a repo, package, and fix version directly is worked the same way. First look for a matching open `[Vanta] Remediate` issue and use it if found. Otherwise skip every Linear step, and name the branch `fix/<package slug>`. With neither, take Todo issues in the configured project whose titles start `[Vanta] Remediate`, highest priority first, then earliest due date, up to 5 per run. With a request to "include assessments", also take Todo `[Vanta] Assess` issues.
- **Mode**: apply by default. A dry run patches and verifies in a worktree but does not push, open PRs, or write to Linear; it reports the diff and keeps the worktree for inspection.
- **Configuration**: the Linear team, project and assignee, and the image-to-repo map, are in vanta-triage's `references/config.json`: team **Product Engineering**, project **AppSec (ongoing)**, GitHub org **cipherstash**. Repos are looked up locally under `$VANTA_REPOS_BASE` (default `~/src`) before cloning.

Needs `git`, `gh` authenticated with push access, Python 3, the target ecosystem's toolchain (`cargo`, `pnpm`/`npm`/`yarn`/`bun`, `go`, `poetry`/`uv`), and the Linear connector's tools. In Claude Code routines the GitHub proxy rejects GraphQL, so `gh pr create` fails: open PRs with `gh api` REST calls as below everywhere.

## Per issue

Process issues one at a time. Each issue ends in exactly one outcome: **PR opened**, **existing PR linked**, **already fixed**, **blocked**, or **skipped**. Record it with the evidence.

1. **Read the issue.** `get_issue` with `description`, `status`, `attachments`. An **In Review** issue with an open PR attached is in flight: skip it.
   - **`[Vanta] Assess` issues** have no target version: Vanta often reports no fix, and deps.py does not read OS packages. Take the images, source repo, package, and advisories from the description, make the worktree as in step 3, then follow [references/containers.md](references/containers.md) in place of steps 2 and 4–6. Its outcomes map onto this skill's: a base-refresh or trimmed-install PR goes through step 7, and the rest are comments that leave the issue open.
   - **`[Vanta] Remediate` issues.** Take repo, ecosystem, and package from the `Vanta key:` line (`dependency:<owner/repo>:<ecosystem>:<package>`), or from the `**Package:**` and `**Repo:**` lines and the title on older issues. Spell the package as the `**Package:**` line does: keys on older issues are lowercased, and Go module paths are case-sensitive. Take targets from the title's `to …` (versions split on ` / `), and the affected ranges from the advisory table's Affected column, one per row.
   - Use the affected ranges only when each row's "Fixed in" version is one of the title's targets. A mismatch means the table predates a retarget. Run deps.py with `--target` alone then, because a stale range can pass a version the new target still rejects.
   - A Remediate issue that does not resolve to a repo, package, and target is **skipped**, with the reason in the report.

2. **Check for a PR already in flight.** Run `gh api --paginate "repos/<owner/repo>/pulls?state=open&per_page=100" --jq '.[] | {number, title, head: .head.ref, user: .user.login}'` and look for a PR, from Dependabot or a person, whose title or head branch names the package.
   - A title alone proves nothing: Dependabot often bumps one `package.json` without touching the lockfile. Verify each candidate with deps.py (step 4's command) on the PR's head. Fetch it with `git -C <clone> fetch origin pull/<n>/head`, then `git -C <clone> worktree add --detach <scratch path> FETCH_HEAD`, and remove that worktree afterwards.
   - If deps.py exits 0 on the PR head, link the PR instead of duplicating it: `save_issue` with `links: [{url, title: "GitHub PR"}]` and `state: "In Review"`, plus a comment carrying the deps.py summary. Outcome **existing PR linked**.
   - If deps.py exits 1, note the PR as incomplete in the report and in the PR body, and continue.

3. **Worktree from the default branch.** Never patch the user's checkout or its branch.
   - Find a clone: `$VANTA_REPOS_BASE/<repo name>` whose `origin` is the repo, else `gh repo clone <owner/repo> <scratch>/<repo name>`.
   - `git -C <clone> fetch origin`, read the default branch from `gh api repos/<owner/repo> --jq .default_branch`, then `git -C <clone> worktree add -B fix/<id lowercased>-<package slug> <path> <base>`, with `origin/<default>` as `<base>`. Use `<clone>-<id lowercased>` as the path for a local clone, or a scratch path otherwise. The package slug is the package name with `@` dropped and `/` turned into `-`.
   - An earlier dry run or blocked run leaves its worktree and local branch behind, and `worktree add` refuses both. If `<path>` exists, run `git -C <clone> worktree remove --force <path>` and `git -C <clone> worktree prune` first. `-B` then resets the leftover local branch, which holds no commits because only step 7 commits.
   - If the branch already exists on `origin`, a previous run pushed it. If it has an open PR, go to step 2's linking. Otherwise use `origin/<branch>` as `<base>` and continue. This is a **resumed** fix: the branch may already carry the patch while the default branch does not.

4. **Measure.** `python3 <skill dir>/scripts/deps.py <worktree> --ecosystem <eco> --package <pkg> --target <v> … --affected "<range>" …`.
   - For a resumed fix, the worktree is the fix branch, not the default branch. Measure `origin/<default>` separately, in a detached worktree (`git -C <clone> worktree add --detach <scratch path> origin/<default>`, removed afterwards). Only that result can make the outcome **already fixed**. If the default branch is still vulnerable and the resumed worktree already passes, skip step 5, run step 6's checks on the worktree, and continue to step 7 to open the PR.
   - Exit 0 on the default branch means nothing resolved is vulnerable there: the package is gone or already patched. Mark the issue **Done** with a comment carrying the deps.py summary and the commit sha. Vanta clears it on its next scan, and vanta-triage reports it as awaiting rescan until then. Outcome **already fixed**. Exit 1 lists every lockfile and version to fix. Exit 2 means a lockfile could not be read (named in `unsupported`): nothing can be claimed fixed until it is, so the outcome is **blocked** with the file and error. Note other `unsupported` lockfiles: they must be checked by hand before claiming a fix.

5. **Patch.** Follow [references/ecosystems.md](references/ecosystems.md) for the ecosystem. It escalates from an in-range update, to a manifest bump, to an override, and says when to stop. Fix every lockfile deps.py listed, not only the root one.

6. **Verify.** Re-run deps.py with the same arguments. It must exit 0. Then:
   - Run the ecosystem's lockfile consistency check from ecosystems.md.
   - Run `git diff --stat`. Only manifests and lockfiles may change, plus a Dockerfile for a container fix. Any other changed file means the toolchain did something unexpected: discard the worktree and treat the issue as blocked.

   CI runs the test suites, so don't run them locally.

   If no version reaches the target, or reaching it needs more than ecosystems.md allows, the outcome is **blocked**. Comment on the issue with what pins the old version (the dependents chain from `cargo tree -i`, `pnpm why`, `npm explain`, or `go mod why`), the deps.py output, and the smallest change that would unblock it. Leave the issue in Todo.

7. **Commit and open the PR** (skip in dry-run mode).
   - Commit message: `fix(deps): patch <package> to <landed version(s)>`. Leave out the Linear id: some repos are open source, and the branch name already carries the id, which Linear's GitHub integration links on.
   - Push with `git push -u origin <branch>`, then open the PR:

     ```sh
     gh api repos/<owner/repo>/pulls -f title='fix(deps): patch <package> to <version>' -f head=<branch> -f base=<default> -F body=@<scratch>/pr-body.md -F draft=<true|false>
     ```

     `-F` reads a value starting with `@` from that file and sends `true`/`false` as booleans; `-f` sends its value verbatim. Keep `-f` for title, head, and base.

   - PR body: each advisory (id, link, severity), each lockfile's version before and after, and the verification run. Draft when the patch changed a direct dependency's major line (0.x minor counts as major), and say why in the body.
   - Linear:
     - `save_issue` with `links: [{url: <PR url>, title: "GitHub PR"}]` and `state: "In Review"`.
     - A comment summarising the before and after versions, plus the draft reason when the PR is a draft.
   - Remove the worktree with `git worktree remove`. Keep the branch.

   Outcome **PR opened**.

## Report

One line per issue: id, outcome, repo, package, versions before → after, the PR link or the reason. Then anything unsupported, blocked, or needing a human decision (draft major bumps, container determinations to file in Vanta). In dry-run mode, list each worktree path and its diff stat, and say plainly that nothing was pushed or written.

## Boundaries

- Never force-push, rewrite a branch that has a PR with review activity, merge PRs, or push to a default branch.
- Never weaken a lockfile check (`--no-frozen-lockfile` in CI config, deleting a lockfile to regenerate everything) to make a bump pass. Regenerating one ecosystem's lockfile is allowed only where ecosystems.md says so.
- Close nothing on the strength of a PR alone; vanta-triage closes issues when Vanta stops reporting them. The one exception is step 4's already-fixed case, which rests on lockfile evidence.
