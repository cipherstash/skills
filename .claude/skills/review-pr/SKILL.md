---
name: review-pr
description: Runs the review-pr workflow, which reviews one pull request with an independent reviewer per dimension, has a separate agent try to refute each finding, audits the PR's existing feedback, cross-checks and reconciles the counts, and writes a run report. Posts only when asked. Claude Code only. Started by the person, never by the model.
argument-hint: "<PR number or URL> [post] [no-audit] [only <dimension,...>]"
disable-model-invocation: true
---

# review-pr

Start the `review-pr` workflow in `.claude/workflows/review-pr.js`. The person typing this command is their opt-in to a multi-agent run. The Workflow tool does the work. This session does not.

This runs in Claude Code only. Codex cannot run workflows. In Codex, say that and stop.

1. Find the script. Run `git rev-parse --show-toplevel` in the checkout of the skills repository. That is the working directory, or the checkout under it if the session starts outside the repository. The script is `<top>/.claude/workflows/review-pr.js`. If it is not there, stop and say which path you checked.
2. Build `args` from the command's arguments:
   - a number or a pull request URL is `pr`;
   - `post` sets `post: true`;
   - `no-audit` sets `audit: false`;
   - `only correctness,lang-go` sets `dimensions: ["correctness", "lang-go"]`.

   With no pull request, ask for one. For a PR in another repository given by number, add `repo: "<owner>/<name>"`. Pass `args` as a JSON object, not a string.
3. Call the Workflow tool with `scriptPath` set to the script's absolute path and `args`. Say in one line that it has started, and whether it will post.
4. When it finishes, give the person its run report: the head commit reviewed, the reconciled counts, the new findings most severe first, the questions that need them, and the review's link if it posted. If the counts did not reconcile, say so first.

Without `post` the run writes nothing to GitHub. Never push, resolve threads, approve or merge while it runs.
