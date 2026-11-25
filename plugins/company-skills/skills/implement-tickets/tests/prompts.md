# Behavior cases

`implement-tickets` is started only by a person typing the command. Claude Code never loads it on its own (`disable-model-invocation: true`), and Codex never selects it implicitly (`agents/openai.yaml`). "Should activate" lists commands a person types.

## Should activate

- `/implement-tickets 56`: starts the workflow with `{spec: 56}`.
- `/implement-tickets 56 plan`: starts it with `{spec: 56, planOnly: true}` and returns the plan without building.
- `/implement-tickets tickets 57,58 base feat/x rounds 3`: starts it with `{tickets: [57, 58], base: "feat/x", maxFixRounds: 3}`.
- `/implement-tickets` with no arguments: asks for the spec issue number and starts nothing until it has one.

## Should not activate

- "Implement the tickets for spec 56" with no command typed: the model never starts a multi-agent run on its own.
- "Review PR 118": a review, not a build.
- "Break spec 56 into tickets": filing tickets comes before this workflow.

## Expected behavior

- In a session whose working directory is any repository, not only this one, the command resolves the script from the installed skill's directory and calls the Workflow tool with that absolute `scriptPath` and `args` as a JSON object.
- If the script is missing from the skill's directory, the skill stops and names the path it checked. It never searches the working directory for a copy.
- In Codex, the skill says that workflows need Claude Code and stops.
- When the run ends, the reply gives the run report and lists each PR with its place in the stack, CI state, and open findings.
- The session never merges a PR, marks one ready, or changes its tickets while the run is going.
