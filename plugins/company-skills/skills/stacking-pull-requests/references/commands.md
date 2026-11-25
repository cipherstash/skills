# `gh stack` commands and exit codes

Read this when you need a command's non-interactive form, or when a `gh stack` command exits with a code other than 0.
Checked against `gh stack` 0.3.0.

## Commands that never prompt

Some commands open a prompt or a full-screen view when they detect a terminal.
Give every command its arguments.

| Run this | Not this |
|---|---|
| `gh stack init --base <base> <branch> ...` | `gh stack init` with no branch |
| `gh stack add <branch>` | `gh stack add` with no branch name |
| `gh stack submit --auto --remote origin` | `gh stack submit` |
| `gh stack view --json` | `gh stack view` |
| `gh stack checkout <stack, pull request or branch>` | `gh stack checkout` with no argument |
| `gh stack up`, `down`, `top`, or `bottom` | `gh stack switch` |
| `gh stack merge <pull request> --yes --merge` | `gh pr merge` on a pull request in a stack |

- Never run `gh stack modify`, because the command works only in a full-screen view. If a command reports a paused `modify` session with exit code 10, run `gh stack modify --abort`.
- Pass `--remote origin` to `push`, `submit`, `sync`, `rebase`, and `link`. Without that flag, gh-stack stops in a clone with several remotes and no default remote.
- `gh stack <command> --help` lists a command's flags. `gh stack help <command>` prints only the general help.

## Exit codes

gh-stack defines these codes in `cmd/utils.go`, checked at v0.3.0.

| Code | Meaning | What to do |
|---:|---|---|
| 1 | The command failed, and has already printed the error. | Read the error, then stop and tell the user. |
| 2 | The branch is not in a stack. | Run `gh stack init` or `gh stack checkout <target>`. |
| 3 | A rebase stopped on a conflict. | Fix the files, run `git add`, then run `gh stack rebase --continue`. |
| 4 | A GitHub API call failed. | Run `gh auth status`, then try again. |
| 5 | The arguments are not valid. `gh stack merge` also returns 5 for a draft, a closed pull request, or one outside the stack. | Read the error. For a draft, ask the user. Do not mark it ready yourself. |
| 6 | gh-stack cannot choose between several stacks or remotes. | Check out a branch that only one stack contains, and pass `--remote origin`. |
| 7 | A rebase is already in progress. | Run `gh stack rebase --continue` or `gh stack rebase --abort`. |
| 8 | Another `gh stack` command has taken the lock. | Wait, then try again. Do not delete the lock file. |
| 9 | GitHub refused the Stacks API. | Tell the user. Do not build a chain by hand. |
| 10 | A `modify` session is paused. | Run `gh stack modify --abort`. |

For any code that this table does not list, stop and tell the user.

`sync` exits with code 0 when the local stack and the stack on GitHub have diverged.
In that case, `sync` prints `Sync aborted` and changes nothing.
Check the output for that message.
