# Behavior cases

The alias sets `disable-model-invocation: true` (Claude Code) and `allow_implicit_invocation: false` (Codex), so it activates only when invoked by name and never competes with `review-audit`.

## Should activate

- `/audit-pr-feedback` with the inputs `review-audit` takes.

## Should not activate

- Any request that does not name `audit-pr-feedback` — `review-audit` handles it.

## Expected behavior

- The agent loads `review-audit`'s `SKILL.md` and follows it with the same arguments and pasted input; the outcome matches invoking `review-audit` directly.
- The user is told once that `audit-pr-feedback` is deprecated in favour of `review-audit`.
