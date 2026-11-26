---
name: implement-tickets
description: Runs the implement-tickets workflow, which builds a spec's ready-for-agent tickets into a chain of draft PRs, reviews and fixes them, and writes a run report. Claude Code only. Started by the person, never by the model.
argument-hint: "<spec issue number> [plan] [tickets 12,13] [base <branch>] [rounds <n>] [routine on|off]"
disable-model-invocation: true
---

# implement-tickets

Start the `implement-tickets` workflow in this skill's `workflows/implement-tickets.js`. The person typing this command is their opt-in to a multi-agent run. The Workflow tool does the work. This session does not.

This runs in Claude Code only. Codex cannot run workflows. In Codex, say that and stop.

1. Find the script. It ships with this skill, at `${CLAUDE_SKILL_DIR}/workflows/implement-tickets.js`. Claude Code fills in `${CLAUDE_SKILL_DIR}` with this skill's installed directory, which is also the "Base directory for this skill" shown when it loads. Never look for it in the working directory or its git checkout. If the file is not there, stop and say which path you checked.
2. Build `args` from the command's arguments:
   - a bare number is `spec`;
   - `plan` sets `planOnly: true`;
   - `tickets 12,13` sets `tickets: [12, 13]`;
   - `base <branch>` sets `base`;
   - `rounds <n>` sets `maxFixRounds`;
   - `routine on` or `routine off` sets `routine` to true or false. Leave it out to let the run check for `.github/workflows/claude-review.yml`.

   With no spec and no tickets, ask for the spec issue number. Pass `args` as a JSON object, not a string.
3. Call the Workflow tool with `scriptPath` set to the script's absolute path and `args`. Say in one line that it has started, and what it will build.
4. When it finishes, give the person its run report. List each PR it opened or updated, with its place in the chain, CI state, and open findings.

Never merge a PR, mark one ready, or change its tickets while the run is going. The workflow's own rules apply to every agent it starts.
