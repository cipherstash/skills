# Behavior cases

The alias sets `disable-model-invocation: true` (Claude Code) and `allow_implicit_invocation: false` (Codex), so it activates only when invoked by name and never competes with `review-fix`.

## Should activate

- `/address-code-review` with the inputs `review-fix` takes.

## Should not activate

- Any request that does not name `address-code-review` — `review-fix` handles it.

## Expected behavior

- The agent loads `review-fix`'s `SKILL.md` and follows it with the same arguments and pasted input; the outcome matches invoking `review-fix` directly.
- The user is told once that `address-code-review` is deprecated in favour of `review-fix`.
