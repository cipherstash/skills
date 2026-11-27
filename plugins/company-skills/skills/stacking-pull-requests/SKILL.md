---
name: stacking-pull-requests
description: Builds and maintains a GitHub stack of pull requests with GitHub's gh-stack extension, so pull requests that each need the code in the one below are linked, rebased, and merged as one stack. Use when the user asks for a stack, a PR stack, or stacked pull requests; when splitting one change into pull requests that each need the one below; or when updating, syncing, re-signing, restructuring, or merging an existing stack. Not for a single pull request or independent ones (authoring-pull-requests), or for the chain of pull requests that the implement-tickets workflow builds.
---

# stacking-pull-requests

Build pull requests that depend on each other as a GitHub stack, with GitHub's gh-stack extension.
The extension adds the `gh stack` command.
Do not build a chain by hand.
Setting each pull request's base branch to the branch below it makes a chain, not a stack.
GitHub treats each pull request in a chain on its own.

This skill adds to authoring-pull-requests.
Use that skill's rules for branch names, commit messages, signed commits, the repository's checks, and each pull request's title and body.
This skill covers what changes when the pull requests form a stack.

The commands were checked against gh-stack 0.3.0 on 20 November 2026.
This is the only place the skill names that version.
On another version, run `gh stack <command> --help` to check the flags.

## What a stack is

A stack is an object that GitHub stores.
The stack links two or more pull requests in a single line.
The bottom pull request targets the default branch.
Each pull request above it targets the branch of the pull request below it.

When pull requests are in a stack, GitHub:

- shows a stack map on each pull request
- applies the default branch's rules and checks to every pull request in the stack
- merges a pull request together with every unmerged pull request below it
- rebases the rest of the stack after the bottom pull request merges

For detail on merges, CI, and GitHub's rebase, read the [reference on what GitHub does with a stack](references/github-behavior.md).

## When to use a stack

Build a stack in these cases:

- The user asks for a stack, a "PR stack", or stacked pull requests.
- You split one change into several pull requests, and each needs the code in the pull request below it.

Open independent pull requests against the default branch instead, with authoring-pull-requests.
Each branch in a stack has one branch below it and at most one above it.
A branch might need the code from two other branches.
A stack cannot hold that branch, so tell the user and ask how to split the work.
Every branch must be in the same repository, because GitHub does not support stacks across forks.

## Inputs

- **The repository**: the user's clone, with `origin` on GitHub.
- **The work**: the change to split, or the branches that already exist, in order from the bottom.
- **An existing stack**, if any: a stack number, pull request number, or branch.
- **Draft or ready**: draft unless the user explicitly says to mark pull requests ready.

## 1. Check the tools

1. Run `gh stack --version`. If the command is not found, install the extension with `gh extension install github/gh-stack`. Installing an extension changes the user's `gh` setup, so ask first unless the user already asked for a stack.
2. Run `git config --type=bool --get commit.gpgsign`. `gh stack rebase` and `gh stack sync` run `git rebase` on your machine. Git signs the new commits only when this command prints `true`. Without that setting, `gh stack rebase` also removes signatures from commits it replays. If the command does not print `true`, stop and tell the user. Do not rebase a stack until commits will be signed.
3. Find the default branch as authoring-pull-requests says. Call it `<base>` below.

Run every `gh stack` command with all of its arguments, so that it never opens a prompt or a full-screen view.
Pass `--remote origin` to `push`, `submit`, `sync`, `rebase`, and `link`.
Never run `gh stack modify`, because it works only in a full-screen view.
The [command and exit code reference](references/commands.md) lists the commands to use and avoid. The same reference explains each exit code.

## 2. Check before every rebase or push

Run these checks before each `gh stack rebase`, `sync`, `push`, or `submit`.

1. **Other worktrees.** Run `git worktree list`. gh-stack keeps one list of stacks for the whole clone, and every worktree uses it. `rebase` and `sync` also rebase a stack branch that is checked out in another clean worktree. If another worktree has a branch of this stack checked out, ask the user before you continue.
2. **Commits that someone else pushed.** `push`, `submit`, and `sync` push with `--force-with-lease`. That option refuses to overwrite a branch that changed since the last fetch. These commands fetch each branch immediately before they push it. So the lease never stops them, and the push deletes any commit that someone else pushed. Protect those commits like this:

   - Before you change any branch of the stack, run `git fetch origin`. Then record the commit that GitHub has for each branch:

     ```bash
     git rev-parse origin/<branch>
     ```

     A branch that has never been pushed has no `origin/<branch>`, and the command fails. Record that branch as absent.
   - Before each push, run `git fetch origin` again, and compare each branch's `git rev-parse origin/<branch>` with the commit you recorded.
   - If a branch's commit has changed, someone else pushed to it. `git log --oneline <recorded commit>..origin/<branch>` lists their commits. Bring their work into your branch, or ask the user, before you push.
   - If a branch you recorded as absent now exists on GitHub, someone else pushed it. Ask the user before you push.
   - After each push, record the commits again.

   This check compares commit IDs, not the changes inside the commits. So your own rebases do not trigger it, and it still finds a commit whose message someone else changed.
3. **Signatures.** Run `git log --format='%h %G? %s' origin/<base>..<top branch>`. Read the result as authoring-pull-requests says. To re-sign a branch in a stack, follow the [re-sign steps](references/restructuring.md#re-sign-a-branch-in-a-stack). Never re-sign with `git rebase --force-rebase <base>` on a branch above the bottom, because it replays the branches below as well.

If you push one branch yourself, use `git push --force-with-lease origin <branch>`. Never write a bare `--force`.

## 3. Create the stack

Create the stack before you write the code.
Put the code that other code depends on in the lowest branch.

First, bring your local `<base>` up to date with GitHub's.
`init` records your local `<base>` commit as the start of the stack.
The first `gh stack rebase` or `sync` replaces an out-of-date record.
Before then, the out-of-date record can cause problems if GitHub retargets the stack.

```bash
git fetch origin <base>:<base>
```

Git refuses this command when `<base>` is checked out in any worktree, including the current one.
A fresh clone usually has `<base>` checked out.
In that case, run `git fetch origin`, then run `git merge --ff-only origin/<base>` in the worktree that has `<base>` checked out.
If that worktree is not yours, ask the user first.

Git also refuses when your local `<base>` has commits that GitHub's does not.
If Git refuses for that reason, stop and ask the user.
Never add `+` to the fetch, and never pass `--force`, because either one discards the user's commits.

Then create the first branch and the stack:

```bash
git switch --no-track -c <first branch> origin/<base>
gh stack init --base <base> <first branch>
```

Create the first branch from `origin/<base>` yourself, so that it starts from GitHub's latest commit.
`--no-track` stops a plain `git pull` on that branch from pulling `<base>`.
Write the first part of the change and commit it.

To turn branches that already exist into a stack, update your local `<base>` as above. Then name the branches from the bottom up:

```bash
gh stack init --base <base> <bottom branch> <next branch> <top branch>
```

`init` adopts the branches that exist and creates the others.
`init` pushes nothing.
`init` leaves the current worktree on the top branch, so switch back afterwards if you need another branch.

## 4. Add a branch

Commit your changes first, then add the next branch from the top of the stack:

```bash
gh stack top
gh stack add <next branch>
```

Always name the branch.
With `-m` and no name, `add` makes a name from the date and the commit message.
That name does not follow the type-prefixed branch names.
Uncommitted changes stay in the working tree and move to the new branch.

To change a lower branch, check it out first with `gh stack checkout <branch>`.
Never commit a lower branch's change on a higher branch.

## 5. Push and open the pull requests

Open the pull requests yourself, then link them.
This order keeps the titles and bodies that authoring-pull-requests asks for.

1. Run the checks in step 2.
2. Push every branch: `gh stack push --remote origin`.
3. Open each pull request as a draft, from the bottom up, as authoring-pull-requests says, with two changes. Set each pull request's base to the branch below it, and the bottom one's base to `<base>`. In each body, give the pull request's position in the stack, and name the pull requests below and above it.
   A `Closes #N` line links only the bottom pull request to its issue, because only its base is the default branch. Link each pull request above it to its issue with the linking-github-issues skill.
4. Link them into a stack: `gh stack submit --auto --remote origin`. `submit` finds the open pull requests and creates the stack on GitHub. `submit` does not change their titles or bodies.
5. Check that every pull request is in the stack:

   ```bash
   gh stack view --json
   gh api repos/{owner}/{repo}/pulls/<number> --jq .stack
   ```

   `gh` fills in `{owner}` and `{repo}` from the current clone. The second command prints the stack number, its size, and the pull request's position. If it prints nothing, that pull request is not in a stack.

Never pass `--open` to `submit` or `link`.
That flag marks every pull request in the stack ready for review, including drafts that already exist.

If you skip the third item, `submit --auto` opens draft pull requests itself.
`submit` takes titles from the branch's commit or name, and adds a gh-stack footer to the body.
Then edit each one to meet authoring-pull-requests.

If a command exits with code 9, GitHub refused the Stacks API for the repository.
Tell the user.
Do not build a chain by hand instead.

## 6. Update the stack after a change lower down

Record the commits as step 2 says before you start.

```bash
gh stack checkout <branch to change>
# edit, then commit
gh stack rebase --upstack --remote origin
```

Then run the checks in step 2, push with `gh stack push --remote origin`, and return to the top with `gh stack top`.

If a rebase stops on a conflict, it exits with code 3 and lists the files.
Fix the files, run `git add`, then run `gh stack rebase --continue`.
To undo the whole rebase, run `gh stack rebase --abort`.

## 7. Sync when the default branch moves

Run the checks in step 2, then `gh stack sync --remote origin`.
`sync` fetches, rebases the whole stack onto `<base>`, and pushes.

- If `sync` stops on a conflict, it restores every branch and exits with code 3. Run `gh stack rebase --remote origin` to repeat the rebase, and resolve the conflict. `gh stack rebase` does not push. So then run the checks in step 2, and push with `gh stack push --remote origin`.
- If `sync` prints `Sync aborted`, the local stack and the stack on GitHub have diverged, and nothing changed. `sync` still exits with code 0, so check the output for that message and tell the user.

## 8. After the bottom pull request merges

GitHub retargets the next pull request to `<base>`, rebases the remaining branches, and force-pushes them.
GitHub marks its rebased commits as verified.
GitHub's commits are not signed with the user's key, so the signature check in step 2 does not show `G` for them.
That result is expected after GitHub's rebase. Do not re-sign them unless the user chooses their own signatures.

Your local branches still hold the commits from before GitHub's rebase.
There are two ways to update them.
Ask the user which they want, unless they have already chosen.
If the user has no preference, keep GitHub's commits.

### Keep GitHub's commits

Nothing is pushed.
CI does not run again.

1. For each remaining branch, compare `git rev-parse <branch>` with the commit you recorded in step 2. A different commit means the branch has local work that GitHub does not have. If any branch differs, or you have no record, ask the user before you continue.
2. Run `git worktree list`. Run `git status --porcelain` in each worktree that has a stack branch checked out. If any prints a line, ask the user before you continue.
3. Run `git fetch origin`. Then record each branch's `git rev-parse origin/<branch>` again, as step 2 says. The new commits are GitHub's rebase, not someone else's work.
4. For each remaining branch, run `git switch <branch>`, then `git reset --keep origin/<branch>`. `--keep` never discards uncommitted changes. Git keeps them in the working tree, or stops if they would conflict. If any reset fails, stop before the next branch, and tell the user.
5. Run `gh stack view --json`, and report what it shows for each branch.

Leave the local branch of the merged pull request in place, and tell the user it is there.

The local record that gh-stack keeps may still list the merged branch, with the old commit IDs, until it gets GitHub's data.
That was seen in a test without GitHub, so check the output of `gh stack view --json` carefully.

### Use the user's signatures

Run the checks in step 2, then `gh stack sync --prune --remote origin`.

The command fetches, rebases the local branches, and signs them with the user's key.
The command then force-pushes every remaining branch, replacing GitHub's commits.
That push starts CI again on each remaining pull request.
`--prune` deletes the local branch of the merged pull request.
After the push, record the commits again, as step 2 says.

After every pull request in the stack has merged, GitHub closes the stack.

## 9. Merge only when the user asks

Do not merge a pull request in a stack unless the user asks.
When they ask, use `gh stack merge`, because `gh pr merge` cannot merge a pull request in a stack:

```bash
gh stack merge <pull request number> --yes --<method>
```

- Merging a pull request also merges every unmerged pull request below it. Either all of them merge, or none do.
- Replace `<method>` with `merge`, `squash`, or `rebase`. Always pass a method. Without one, gh-stack uses the method you used last.
- Use a method the repository allows. To list the allowed methods, run `gh api repos/{owner}/{repo} --jq '{merge: .allow_merge_commit, squash: .allow_squash_merge, rebase: .allow_rebase_merge}'`. If more than one is allowed, and neither the repository's checklist nor the user says which, ask.
- `gh stack merge` refuses a draft, and exits with code 5. Do not mark pull requests ready to make the merge work. Ask the user.
- Do not bypass the repository's rules. `gh stack merge --help` says that bypassing merge requirements is not supported for stacks. Stacks do not support auto-merge either.
- Before the merge, check whether `<base>` has a merge queue. Run `gh api repos/{owner}/{repo}/rules/branches/<base>`, and look for a rule of type `merge_queue`.
- With a merge queue, `gh stack merge` adds the stack to the queue, and GitHub merges it later if CI passes. Merge as the user asked. Do not ask again.
- After a merge into a queue, report the pull requests as "added to the merge queue, not merged yet". Never report them as merged. To see whether a pull request has merged, run `gh pr view <number> --json state,mergedAt`.

## Restructure a stack

To reorder, rename, or remove a branch, or to re-sign a branch in the middle, follow the [reference on restructuring a stack](references/restructuring.md).

## Boundaries

- Do not merge, close, unstack, or mark a pull request ready unless the user asks.
- Do not use the **Rebase stack** button on GitHub. The button's commits never carry the user's signature.
- Do not delete gh-stack's lock file. Exit code 8 means another `gh stack` command has taken the lock. Wait, then try again.
- A single pull request, or several independent ones, is authoring-pull-requests.
- Do not fix review findings here. review-fix fixes them on the pull request's branch. This skill then rebases the branches above it, as step 6 says.
- The implement-tickets workflow builds a chain of pull requests, not a stack. Do not run `gh stack` commands on that chain, or convert it to a stack, unless the user asks.

## Report

Give the stack number and each pull request from the bottom up, with its branch, base, draft state, and stack position as `gh api` reported it.
Give each branch's signature status.
Name anything skipped, any check you could not run, and any question you left for the user.
