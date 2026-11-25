# Behavior cases

## Should activate

- "Open these three branches as a PR stack."
- "Split this refactor into a PR for the new types and a PR that uses them, with the second building on the first."
- "main moved ahead; bring my stack up to date."
- "The bottom PR of my stack just merged. Tidy up the rest."
- "Merge the stack up to #1110."
- "Fix the review comments on the second PR in my stack." The agent loads review-fix as well as this skill.
- "Stack these" with no branches named. The agent asks which branches go in the stack, and their order from the bottom.

## Should not activate

- "Open a PR for this fix." A single pull request is authoring-pull-requests.
- "Open separate PRs for the docs change and the dependency bump." Independent pull requests are authoring-pull-requests.
- "/company-skills:implement-tickets 42". The implement-tickets workflow builds its own chain.

## Expected behavior

- The agent never makes a chain by setting base branches alone. The agent links the pull requests with `gh stack submit --auto --remote origin`. Then `gh api repos/{owner}/{repo}/pulls/<number> --jq .stack` prints a stack for each one.
- If `gh stack` is missing, the agent asks before running `gh extension install github/gh-stack`, unless the user already asked for a stack.
- If `git config --get commit.gpgsign` does not print `true`, the agent stops before any rebase or sync and tells the user.
- Every `gh stack` command has its arguments, and `--remote origin` where the command takes it. The agent never runs `gh stack modify`, bare `gh stack submit`, or `gh stack view` without `--json`.
- The agent creates the first branch from `origin/<base>`, not from the local default branch.
- The agent names every branch passed to `gh stack add`, with a type-prefixed name.
- The agent opens the pull requests as drafts from the bottom up, with authoring-pull-requests titles and bodies. Each pull request's base is the branch below it. Each body gives the pull request's position in the stack.
- The agent never passes `--open` to `submit` or `link`. The agent marks no pull request ready unless the user asks.
- Before each rebase, sync, or push, the agent runs `git worktree list`, the check for commits someone else pushed, and the signature check.
- Before the agent changes any stack branch, it records `git rev-parse origin/<branch>` for each branch. Before each push, it fetches and compares. The agent's own rebases do not trigger the check. A commit whose message someone else changed on GitHub does trigger it.
- Before `gh stack init`, the agent updates the local `<base>` to match `origin/<base>`.
- The agent asks the user before continuing when another worktree has a stack branch checked out.
- The agent asks the user before pushing when GitHub has a commit that the local branch lacks.
- The agent never re-signs a branch above the bottom with `git rebase --force-rebase <base>`. Re-signing starts from the lowest unsigned branch, then runs `gh stack rebase --upstack`.
- After the bottom pull request merges, the agent asks the user to choose, unless they already have. One choice keeps GitHub's commits: the agent resets each local branch to `origin/<branch>` and pushes nothing. The other choice runs `sync`. That command replaces GitHub's commits with signed ones, and CI runs again.
- Before those resets, the agent checks for uncommitted changes, other worktrees, and local commits that `git cherry` marks with `+`. The agent asks the user if it finds any.
- `gh stack merge` on a draft exits with code 5. The agent asks the user, and does not mark the pull request ready.
- For review comments on a pull request in a stack, review-fix verifies and fixes the findings on that pull request's branch. This skill then rebases every branch above it with `gh stack rebase --upstack --remote origin`. The agent runs the checks in step 2 before it pushes.
- When `sync` prints `Sync aborted`, the agent tells the user, even though the exit code is 0.
- When a command exits with code 9, the agent tells the user and does not build a chain by hand.
- The agent merges only when asked, with `gh stack merge <number> --yes` and an explicit method flag that the repository allows. The agent never uses `gh pr merge`, a bypass, or the **Rebase stack** button.
- Before a merge, the agent checks `<base>` for a `merge_queue` rule. With a queue, the agent merges without asking again. The agent then reports the pull requests as "added to the merge queue, not merged yet", never as merged.
- The report lists each pull request from the bottom up with its branch, base, draft state, stack position, and signature status.
