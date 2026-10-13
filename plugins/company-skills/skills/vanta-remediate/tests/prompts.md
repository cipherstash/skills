# Behavior cases

`test_deps.py` covers `scripts/deps.py` (lockfile readers for each ecosystem, range and major-line judgement, manifest detection): `python3 -m unittest discover -s tests` from the skill directory.

## Should activate

- `/vanta-remediate CIP-4892`.
- "Open PRs for the outstanding Vanta Remediate issues."
- "Can you patch the rustls vulnerability Vanta flagged in stack?" (resolves to the matching Todo issue)
- "Dry run the Vanta remediation for CIP-4885 so I can see the diff."
- `/vanta-remediate` from a routine with no issue ids: takes up to 5 Todo Remediate issues by priority, then due date.

## Should not activate

- "Check Vanta for new alerts" or "file Linear issues for the new findings" — vanta-triage.
- "Upgrade React to 19 across the monorepo" — a feature upgrade, not a tracked vulnerability.
- "Review Dependabot PR #1135" — a code review.

## Expected behavior

- Repo, ecosystem, package, targets, and affected ranges come from the issue's `Vanta key:` line, title, and advisory table; an issue missing any of them is skipped with the reason.
- An open PR (Dependabot or human) that reaches the target is linked to the issue instead of opening a duplicate.
- Work happens in a git worktree from a freshly fetched `origin/<default>` on branch `fix/<id>-<package>`; the user's checkout and branches are never modified. A worktree or local branch left by an earlier dry or blocked run is removed and reset, not a reason to stop.
- The open-PR check pages through every open PR, not only the first 100.
- `deps.py` exit 0 on the default branch marks the issue Done with the lockfile evidence; no PR is opened.
- Every lockfile `deps.py` lists is patched, including nested workspaces such as `fuzz/` and FFI packages; verification re-runs `deps.py` and must exit 0.
- The diff contains only manifests and lockfiles (plus a Dockerfile for container fixes); anything else discards the attempt.
- A bump that cannot reach the target is reported blocked, with the dependent chain and the unblocking change commented on the issue, and the issue stays in Todo.
- Commits read `fix(deps): patch <package> to <version>` with no Linear id; the PR is opened with `gh api` REST, with the body read from a file via `-F body=@<file>`, as a draft when a direct dependency crosses a major line.
- After a PR opens, the issue gets the PR link attachment, an In Review state, and a before/after comment.
- Container Assess issues are worked only by id or on request, cite sources for every fix or not-affected claim, and leave Vanta determinations to a human.
- Dry-run mode pushes nothing, writes nothing to Linear, and reports each worktree path and diff stat.
- The run never stops to ask a question.
