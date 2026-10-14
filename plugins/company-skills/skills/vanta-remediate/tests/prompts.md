# Behavior cases

Script tests, run with `python3 -m unittest discover -s tests` from the skill directory:

- `test_deps.py` covers `scripts/deps.py`: lockfile readers for each ecosystem, range and major-line judgement, and manifest detection.
- `test_gate.py` covers `scripts/gate.py`. It runs every combination of claim, ref kind, fix exit, residual exit, `unsupported`, scope, and PR base over real deps.py output, and asserts that nothing outside the allowed set passes.
- `test_workspace.py` covers `scripts/workspace.py` against real throwaway repos, one per starting state, and asserts that no state loses a commit or a file.

## Should activate

- `/vanta-remediate CIP-4892`.
- "Open PRs for the outstanding Vanta Remediate issues."
- "Can you patch the rustls vulnerability Vanta flagged in stack?" (resolves to the matching Todo issue)
- "Dry run the Vanta remediation for CIP-4885 so I can see the diff."
- `/vanta-remediate` from a routine with no issue ids: takes Todo Remediate issues by priority, then due date, until 5 succeed or 15 are examined.

## Should not activate

- "Check Vanta for new alerts" or "file Linear issues for the new findings" — vanta-triage.
- "Upgrade React to 19 across the monorepo" — a feature upgrade, not a tracked vulnerability.
- "Review Dependabot PR #1135" — a code review.

## Expected behavior

- Repo, ecosystem, package, targets, and affected ranges come from the issue's `Vanta key:` line, title, and advisory table; an issue missing any of them is skipped with the reason.
- An open PR into the default branch (Dependabot or human) whose merge ref passes `gate.py --claim linked` is linked to the issue instead of opening a duplicate. It is measured on the PR head, saying so, only when GitHub has no merge ref.
- Work happens in a git worktree that `workspace.py --create` makes, from a freshly fetched `origin/<default>` (or `origin/<branch>` when resumed), on branch `fix/<id>-<package>`; the user's checkout and branches are never modified. Any existing worktree or directory at the path blocks the issue, and so does a local branch with commits beyond the base. Given a dry run that left `<clone>-cip-123` on `fix/cip-123-pkg`, after which the user edited files and committed there, the next run never runs `git worktree remove --force` or `worktree add -B` over it: the issue is **blocked**, the report names the path and why, and nothing is deleted. `workspace.py --cleanup` removes only a worktree whose ownership marker holds this run's id, so a scheduled run is not blocked by its own leftovers. Covered by `test_workspace.py`.
- The open-PR check pages through every open PR, not only the first 100.
- A passing `gate.py --claim already-fixed --ref-kind default` on `origin/<default>` marks the issue Done with the lockfile evidence and the commit sha; no PR is opened.
- Every lockfile `deps.py` lists is patched, including nested workspaces such as `fuzz/` and FFI packages; verification re-runs `deps.py`, and `gate.py --claim opened` must pass.
- The branch's diff against its merge-base with the default branch contains only manifests and lockfiles (only Dockerfiles for container fixes); anything else blocks the issue. Covered by `test_gate.py`.
- A bump that cannot reach the target is reported blocked, with the dependent chain and the unblocking change commented on the issue, and the issue stays in Todo.
- Commits read `fix(deps): patch <package> to <version>` with no Linear id; the PR is opened with `gh api` REST, with the body read from a file via `-F body=@<file>`, as a draft when a direct dependency crosses a major line.
- After a PR opens, the issue gets the PR link attachment, an In Review state, and a before/after comment.
- Assess issues go to `references/containers.md` once the worktree exists, without needing a target version or running deps.py; their outcomes come from `gate.py --claim container`.
- A resumed fix branch already pushed by an earlier run is never treated as "already fixed"; only a passing gate on `origin/<default>` is (`--ref-kind fix-branch` never passes already-fixed, covered by `test_gate.py`), and a passing resumed branch goes on to open its PR.
- Fixed rows' affected ranges whose highest "Fixed in" per major line no longer matches the title's targets are dropped in favour of `--target` alone; `none` rows are never dropped.
- An issue whose `Vanta key:` second segment is a Vanta asset name (an `**Asset:**` line, no `**Repo:**`) is skipped as having no repo; the asset name is never cloned or searched for.
- A Fixed in of `none` is an advisory with no fix yet, not a sign of a stale table. For an issue titled `to 1.2.3` whose table has one row Fixed in `1.2.3` and another Fixed in `none`, Affected `>= 1.0.0, < 2.0.0`, the `none` row's range is still checked: a lockfile at `1.2.3` does not count as fully remediated and the issue is never marked Done while that range still matches. Rows Fixed in a lower version on the same major line as a target (for example `1.2.0` beside `1.2.3`) are not stale either.
- Container Assess issues are worked only by id or on request, cite sources for every fix or not-affected claim, and leave Vanta determinations to a human.
- Dry-run mode pushes nothing, writes nothing to Linear, keeps a worktree only when it holds a diff, and reports each kept worktree's path and diff stat.
- The run never stops to ask a question.

### Resumed work and evidence (R3)

- R3a. CIP-7 was In Review with PR #40 from `fix/cip-7-lodash`; triage retargeted it to a higher version and moved it to Todo. Step 3 finds PR #40, whose head fails the new fix check. The run resumes on `origin/fix/cip-7-lodash`, patches on top, pushes a fast-forward to that branch, and updates PR #40's body; it never calls the create-PR endpoint, never opens a second PR, and never force-pushes. The issue moves to In Review only once the new head passes `gate.py --claim opened`. Covered by `test_workspace.py` (`test_own_open_pr_resumes_and_names_it`).
- R3b. A local branch `fix/cip-8-rustls` holds a commit a human made, never pushed, and no worktree exists for it. `workspace.py` checks the branch before `worktree add` (`git worktree add -B` resets such a branch silently, it does not refuse): the outcome is **blocked**, the report names the commit, and the branch still points at it afterwards. Covered by `test_workspace.py` (`test_local_branch_with_human_commit_blocks`).
- R3c. A dry run left `<clone>-cip-9` with its patch uncommitted, and the user added a gitignored `.env.local` there. `git status --porcelain` prints nothing for the ignored file, but `git worktree remove` would delete it. The next run treats any existing worktree at `<path>` as **blocked** and deletes nothing, whether or not it looks clean. A dry run whose outcome left no diff removes its own worktree before it finishes. Covered by `test_workspace.py` (the `test_leftover_*` and `TestCleanup` cases).
- R3d. `fix/cip-10-serde` was pushed by an earlier run; a human then pushed a commit there that also edits `src/lib.rs`. The resumed worktree already passes the fix check. The run checks the whole branch against its merge-base with `origin/<default>`, not only uncommitted changes: the source edit makes the outcome **blocked**, and no PR is opened. When the branch holds only manifest and lockfile changes, the run opens the PR without making an empty commit. Covered by `test_workspace.py` (`test_remote_branch_with_human_commit_resumes_with_evidence`) and `test_gate.py` (`test_r3d_source_change_on_resumed_branch_blocks`).
- R3e. An open PR that bumps the package targets `release/1.x`, not the default branch, and its head passes the fix check. It is never linked: only PRs whose base is the default branch are candidates. Covered by `test_gate.py` (`test_r3e_pr_into_another_branch_is_not_linked`).
- R3f. The default branch has no readable lockfile for the package, only a binary `bun.lockb`: deps.py exits 0 with `bun.lockb` in `unsupported`. The issue is **blocked** with that file named, never Done. Likewise a candidate PR whose head makes deps.py exit 2 is not linked, and a residual check that exits 2 never allows Done, linking, or In Review. A package locked without a resolved version (deps.py exit 2) blocks too. Covered by `test_gate.py` (the `test_r3f_*` cases and the combination property).
- R3g. CIP-11 is In Review with an open PR; triage then refreshed its description with a new advisory Fixed in `none`, leaving it In Review. The next run does not skip it: the `Advisory set:` digest differs from the one this skill recorded when it moved the issue to In Review, so the run measures the PR again, residual check included, comments the newly unfixed advisory, and moves the issue to Todo if the gate fails. No executable test: prose instruction (SKILL.md step 1).
- R3h. CIP-12's PR merged, but its `none` advisory still matches on the default branch, so the issue sits In Review with no open PR. The next run's outcome is **blocked** with the residual summary, and it moves the issue back to Todo rather than leaving it In Review. No executable test: prose instruction (SKILL.md, Blocked outcomes).
- R3j. A scheduled run's queue starts with six high-priority issues that are skipped (asset-name keys) or blocked (a leftover worktree). Those do not use up the run's five slots: the run keeps taking issues until five have succeeded or fifteen have been examined. It does not repeat a blocked comment when the evidence is unchanged since its last one. No executable test: prose instruction (SKILL.md Inputs and Blocked outcomes).
- R3k. An Assess issue covers `zerokms + cts images` with three advisories: one fixed in the base suite, one not affected, and one unfixed. The run reads every image on the generated section's `**Images:**` line and records a determination for every advisory row. A base-refresh PR may open, but the issue moves to In Review only if a rebuilt image of every listed image shows a fixed package version for every advisory. Here it stays in Todo, with a comment listing the advisories the PR does not clear. When no container runtime is available, the PR opens as a draft marked unverified and the issue stays in Todo. An Assess issue whose source repo is unknown is skipped. Covered by `test_gate.py` (`TestContainerGate`).
- R2g. A legacy issue had triage's generated section prepended above a `---` rule, and kept its old text below, including an older `### Advisories` table whose rows list a lower Fixed in and a different Affected range. The run reads the `**Package:**` and `**Repo:**` lines, the advisory table, and the `Advisory set:` value only from the generated section: the first `## Vulnerability` heading through the first `Vanta key:` line after it. The old table's ranges are never passed to deps.py and never count toward the staleness check. No executable test: prose instruction (SKILL.md step 1).
- R3l. A direct request "patch lodash to 4.17.21 in cipherstash/stack" with no matching issue uses the branch `fix/vanta-lodash`. A human's existing `fix/lodash` branch on origin is never resumed or pushed to, and `workspace.py` refuses any branch outside the `fix/<id>-` and `fix/vanta-` shapes. Covered by `test_workspace.py` (`test_human_branch_name_is_never_adopted`).
