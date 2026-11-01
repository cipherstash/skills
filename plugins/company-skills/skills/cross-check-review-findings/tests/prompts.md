# Behavior cases

The alias sets `disable-model-invocation: true` (Claude Code) and `allow_implicit_invocation: false` (Codex), so it activates only when invoked by name and never competes with `review-cross-check`.

## Should activate

- `/cross-check-review-findings` with the inputs `review-cross-check` takes.

## Should not activate

- Any request that does not name `cross-check-review-findings` — `review-cross-check` handles it.

## Expected behavior

- The agent loads `review-cross-check`'s `SKILL.md` and follows it with the same arguments and pasted input; the outcome matches invoking `review-cross-check` directly.
- The user is told once that `cross-check-review-findings` is deprecated in favour of `review-cross-check`.
