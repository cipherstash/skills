---
name: implement-tickets
description: Runs the implement-tickets workflow, which builds a spec's ready-for-agent tickets into stacked draft PRs, reviews and fixes them, and writes a run report. Claude Code only. Started by the person, never by the model.
argument-hint: "<spec issue number> [plan] [tickets 12,13] [base <branch>] [rounds <n>]"
disable-model-invocation: true
---

# implement-tickets

Start the `implement-tickets` workflow in `.claude/workflows/implement-tickets.js`. The person typing this command is their opt-in to a multi-agent run. The Workflow tool does the work. This session does not.

This runs in Claude Code only. Codex cannot run workflows. In Codex, say that and stop.

1. Find the script. Run `git rev-parse --show-toplevel` in the checkout of the skills repository. That is the working directory, or the checkout under it if the session starts outside the repository. The script is `<top>/.claude/workflows/implement-tickets.js`. If it is not there, stop and say which path you checked.
2. Build `args` from the command's arguments:
   - a bare number is `spec`;
   - `plan` sets `planOnly: true`;
   - `tickets 12,13` sets `tickets: [12, 13]`;
   - `base <branch>` sets `base`;
   - `rounds <n>` sets `maxFixRounds`.

   With no spec and no tickets, ask for the spec issue number. Pass `args` as a JSON object, not a string.
3. Call the Workflow tool with `scriptPath` set to the script's absolute path and `args`. Say in one line that it has started, and what it will build.
4. When it finishes, give the person its run report. List each PR it opened or updated, with its place in the stack, CI state, and open findings.

Never merge a PR, mark one ready, or change its tickets while the run is going. The workflow's own rules apply to every agent it starts.
