# Behavior cases

`review-pr` is started only by a person typing the command. Claude Code never loads it on its own (`disable-model-invocation: true`), and Codex never selects it implicitly (`agents/openai.yaml`). "Should activate" lists commands a person types.

## Should activate

- `/review-pr 118`: starts the workflow with `{pr: 118}` and writes nothing to GitHub.
- `/review-pr https://github.com/cipherstash/skills/pull/118 post`: starts it with that URL as `pr` and `post: true`.
- `/review-pr 118 no-audit only correctness,lang-go`: starts it with `{pr: 118, audit: false, dimensions: ["correctness", "lang-go"]}`.
- `/review-pr` with no arguments: asks for the pull request and starts nothing until it has one.

## Should not activate

- "Review PR 118" with no command typed: the model never starts a multi-agent run on its own; a single-skill review such as `golang-review` may handle it instead.
- "Post these findings to PR 118": that is `review-post`.
- "Which threads on PR 118 are still open?": that is `review-audit`.

## Expected behavior

- In a session whose working directory is any repository, not only this one, the command resolves the script from the installed skill's directory and calls the Workflow tool with that absolute `scriptPath` and `args` as a JSON object.
- If the script is missing from the skill's directory, the skill stops and names the path it checked. It never searches the working directory for a copy.
- In Codex, the skill says that workflows need Claude Code and stops.
- When the run ends, the reply gives the head commit reviewed, the reconciled counts, the new findings most severe first, the questions for the person, and the review's link if it posted. Counts that did not reconcile are reported first.
- Without `post`, nothing is written to GitHub. The session never pushes, resolves threads, approves or merges.
