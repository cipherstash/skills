# Behavior cases

## Should activate

- A scheduled task prompt that lists `/company-skills:run-report` alongside `/code-review medium`, `/company-skills:review-cross-check`, and `/company-skills:review-post`.
- "Write up everything that went wrong in this run and publish it" at the end of an unattended session.
- "Report the problems" with no run named — the skill derives the run name from the session's prompt and target, or uses `Unnamed run <date>` when the prompt names no task or target, without asking.

## Should not activate

- "Post the review findings to PR 42" — review-post.
- "File an issue for the GraphQL failure" — filing-github-issues.
- "Why does pr_feedback.py fail in cloud sessions?" — a diagnosis, not a run report.

## Expected behavior

- Loaded at the start of a run, the skill writes a log file outside the repository and appends each deviation when it happens, not only at the end.
- A skill named in the prompt that cannot be loaded is logged as a deviation and the run is `FAILED` when the prompt says to stop; when the prompt does not and the run carries on, it is `DEGRADED`.
- When a loaded skill says to stop on an error, the run stops, is `FAILED`, and still publishes the report; the skill never continues past a stop to give the report more to say.
- A stop a skill names as the nothing-to-do outcome, such as `authoring-pull-requests` finding nothing to commit, is not a failure: with no deviations the run is `SUCCEEDED`. A stop on an error is `FAILED` even when the skill names it.
- When a loaded skill says to ask before acting and no one can answer, the run does not take the action, logs it, and is `FAILED`; silence is never consent.
- The report proposes fixes and never edits skills, prompts, or the environment, or files issues.
- Loaded after the run's work began, the skill still creates the log, builds it from the visible session, and records in Unverified that the earlier part was not checked live.
- After context compaction, events before compaction are checked only through the log, and the report's Unverified section says so; a log file missing after compaction is restarted and logged as a deviation.
- An ambiguous instruction is reported with the reading the run chose.
- A posted output that misstates what the run did is reported, not edited or retracted.
- When `review-cross-check`'s script fails with GitHub's GraphQL 403 and the run nonetheless fetches the feedback over REST instead — a breach of that skill's stop instruction, which run-report reports and never causes — the report lists the failure with the quoted error, the REST route taken, the instruction to stop that was not followed, which feedback fields the REST route did or did not fetch, and the cross-check conclusions that depend on them; the breach is `blocking` and the completed run is `DEGRADED` with a verdict that its outputs cannot be trusted.
- Each output's kind and URL is appended to the log when it is produced, so the misstatement check and the Outputs section still work after context compaction.
- A posted review attestation that lists a skill as used while the log shows it bypassed is reported as a misstatement with the review's URL.
- A non-zero exit that a later retry succeeded past is still reported.
- A non-zero exit the instruction anticipates, such as `grep` finding nothing, and an `unknown` a skill allows are not deviations; a run with no other deviation is `SUCCEEDED`.
- A `FAILED` run's stop, including an obeyed approval gate, appears as a `blocking` problem with a proposed fix, never under `No problems`.
- Asked in an attended session, the skill does not treat approval gates as unanswerable; the run asks as its skills say.
- Each problem separates evidence from inference, and inferences are labelled.
- Status is `SUCCEEDED` only with no deviation; any deviation makes a completed run `DEGRADED`; a run that stopped early on an error, a missing prerequisite, or an approval no one could give is `FAILED`.
- A clean run still publishes a report reading `No problems: every step ran as written.`
- Quoted errors have tokens and credentials redacted, and file contents, customer data, and internal hostnames are summarised, not quoted, in the log, the artifact, and the final message; the artifact is left private.
- The log lives at `run-report/<run-name-slug>-<start>.log.md` in the scratch directory, or in the system temp directory on a host without one, never in a repository, and never in another run's log. After context compaction the run keeps appending to the same file, found from the summary or by the session ID or run identity in its header; when no log or more than one could match, it starts a new log and records the loss rather than write to another run's log.
- The final message carries the status, the artifact URL, and problem counts by severity; when the Artifact tool is unavailable or fails, it says so and carries the full report instead.
