# Behavior cases

## Should activate

- A scheduled task prompt that lists `/company-skills:run-report` alongside `/code-review medium`, `/company-skills:review-cross-check`, and `/company-skills:review-post`.
- "Write up everything that went wrong in this run and publish it" at the end of an unattended session.
- "Report the problems" with no run named — the skill derives the run name from the session's prompt and target, or uses `Unnamed run <date>` when there is neither, without asking.

## Should not activate

- "Post the review findings to PR 42" — review-post.
- "File an issue for the GraphQL failure" — filing-github-issues.
- "Why does pr_feedback.py fail in cloud sessions?" — a diagnosis, not a run report.

## Expected behavior

- Loaded at the start of a run, the skill writes a log file outside the repository and appends each deviation when it happens, not only at the end.
- A skill named in the prompt that cannot be loaded is logged as a deviation and the run is `FAILED` when the prompt says to stop.
- When `review-cross-check`'s script fails with GitHub's GraphQL 403 and the run fetches the feedback over REST instead, the report lists the failure with the quoted error, the REST route taken, the instruction to stop that was not followed, which feedback fields the REST route did or did not fetch, and the cross-check conclusions that depend on them.
- A posted review attestation that lists a skill as used while the log shows it bypassed is reported as a misstatement with the review's URL.
- A non-zero exit that a later retry succeeded past is still reported.
- Each problem separates evidence from inference, and inferences are labelled.
- Status is `SUCCEEDED` only with no deviation; any deviation makes a completed run `DEGRADED`; a run that stopped early is `FAILED`.
- A clean run still publishes a report reading `No problems: every step ran as written.`
- Quoted errors have tokens and credentials redacted; file contents, customer data, and internal hostnames are summarised, not quoted, and the artifact is left private.
- The log lives at `run-report-<run-name-slug>.md` in the scratch directory; after context compaction the run re-derives that path and appends to the same file.
- The final message carries the status, the artifact URL, and problem counts by severity; when the Artifact tool is unavailable or fails, it says so and carries the full report instead.
