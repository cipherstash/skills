# Restructure or re-sign a stack

Read this when you need to reorder, rename, or remove a branch in a stack.
Read it also when you need to re-sign commits in a branch above the bottom.

## Re-sign a branch in a stack

Do not run `git rebase --force-rebase <base>` on a branch above the bottom of a stack.
That command replays the commits of the branches below as well.
The branch then no longer starts from the top commit of the branch below it.

Re-sign from the lowest branch that has an unsigned commit.
First check that every commit you will re-sign is the user's or yours, as authoring-pull-requests says.
Check also that `git config --type=bool --get commit.gpgsign` prints `true`.
`--gpg-sign` signs only the commits of the first rebase below.
`gh stack rebase` signs the branches above only when that setting is on.

Record the commits as step 2 of SKILL.md says, before the first command.
Then run:

```bash
gh stack checkout <lowest branch with an unsigned commit>
git rebase --force-rebase --gpg-sign <branch below it>
gh stack rebase --upstack --remote origin
git log --format='%h %G? %s' origin/<base>..<top branch>
```

If the lowest unsigned branch is the bottom branch, use this rebase instead of the second command:

```bash
git rebase --force-rebase --gpg-sign --keep-base origin/<base>
```

`--keep-base` keeps the branch on the same `<base>` commit.
Without it, the rebase also moves the branch onto newer `<base>` commits.
That move changes the pull request's content, and can stop on conflicts.

`gh stack rebase --upstack` replays every branch above the one you re-signed.
Then run the checks in step 2 of SKILL.md again, and push with `gh stack push --remote origin`.

A test on 25 November 2026 ran this sequence on a stack of three branches, with a local remote and no GitHub.
Every commit ended up signed.
Each branch still started from the top commit of the branch below it.
The changes in each branch stayed the same.
After you run it, check every commit's signature and each pull request's diff, and report the result to the user.

## Reorder, rename, or remove a branch

`gh stack` has no command that reorders a stack without a full-screen view.
`gh stack unstack` removes the stack on GitHub, so ask the user before step 1.
`gh stack submit` force-pushes the rewritten branches in step 4.
So record the commits as step 2 of SKILL.md says before step 1.

1. Run `gh stack unstack`. The command removes the stack on GitHub and the local record. The branches and pull requests stay.
2. Change the branches with git. Put the commits in the new order first.
3. Run `gh stack init --base <base> <branches from the bottom up>`.
4. Run the checks in step 2 of SKILL.md again. Then run `gh stack submit --auto --remote origin` to push the branches and link the pull requests again.
5. Check each pull request with `gh api repos/{owner}/{repo}/pulls/<number> --jq .stack`.

GitHub keeps merged and queued pull requests in their stack.
`unstack` cannot remove them.

## Link pull requests without a local record

`gh stack link <pull request> <pull request> ...` creates a stack on GitHub without a local record.
Use `link` only when another tool manages the branches.
Navigation commands such as `gh stack up` do not work on a stack that `link` made.
Never pass `--open` to `link`.
