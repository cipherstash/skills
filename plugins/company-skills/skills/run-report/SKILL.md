---
name: run-report
description: Keeps a log of every problem an unattended run hits — errors, failed commands, retries, fallbacks, workarounds, skipped or partial steps, missing skills or access, and assumptions made in place of instructions — then publishes a run report as a Claude artifact with the run's status, an analysis of each problem, and its impact on what the run produced; a clean run still publishes one. Use at the start of a scheduled task, routine, or other unattended run, or when asked to report what went wrong in a run. Does not post review findings (review-post) or file issues (filing-github-issues).
argument-hint: "[run name]"
---

# run-report

Make every **deviation** visible. A deviation is any point where the run did not do what its prompt or a skill said, as written: a command that failed, a retry, a fallback route, a workaround, a step skipped or done in part, a value left `unknown`, a gap filled by assumption. A run that patches over a deviation and carries on produces output that looks normal and is not; the report is where the patch shows.

Every run publishes one report. A missing report means the run died before the end.

## Inputs

- The run's prompt and the skills it loaded: the instructions deviations are measured against.
- A run name, if given; otherwise derive one from the prompt and its target, such as `Code review PR 1496`; with neither, `Unnamed run <date>`. Never ask: an unattended run has no one to answer.

## Steps

1. **Open the log.** When loaded at the start of a run, create the log at a fixed path: `run-report-<run name as a lowercase hyphenated slug>.md` in the session's scratch directory, outside any repository. Record the run name, start time, host, model ID, and the prompt's skills, each marked loaded or missing. A missing skill is the first deviation. After context compaction, re-derive the path from the run name and keep appending to that file; when it is missing, start it again and log the loss as a deviation. Completion: the log file exists at that path.

2. **Log as you go.** Continue the run's own work. The moment a deviation happens, append an entry to the log before doing anything else — the log is on disk so it survives context compaction:
   - **Where**: the skill and step, or the prompt line, whose instruction was not followed as written.
   - **What happened**: the command or tool call and its exact error, exit code, or output, quoted. Quote only the lines that show the problem. Redact tokens, secrets, and credentials, and summarise rather than quote file contents, customer data, and internal hostnames.
   - **What the run did instead**: the retry, alternate command or API, manual step, assumption, or skip. When an instruction said to stop and the run continued, say so.

   Completion, checked when the run's work ends: every non-zero exit, tool error, retry, and alternate route in the session has an entry.

3. **Reconcile.** Read back through the whole session — or, when this skill was loaded late, build the log from it now. Hunt for deviations the log missed:
   - non-zero exits and tool errors, including ones a later call succeeded past;
   - retries and timeouts;
   - fallbacks: a different command, API, endpoint, or tool than the one written;
   - steps skipped, partly done, or done out of order;
   - data read in part: truncated output, an unread page, a file too large to read;
   - values reported `unknown` or guessed;
   - instructions that were ambiguous, contradictory, or impossible here, and the reading the run chose;
   - missing skills, tools, permissions, credentials, or network access;
   - warnings the run noted and moved past.

   Then check each output the run produced — a posted review, a comment, a PR, an issue — against the log. An output that names a skill or step as used while the log shows it bypassed or degraded is a **misstatement**: add a deviation naming the output's URL and what it claims. Completion: every item above was checked against the session, and every output was compared with the log.

4. **Analyse.** For each deviation, add:
   - **Impact**: which outputs, findings, or claims rest on it, and what is now unverified or wrong. A fallback that fetched less data than the written route says which data, and which conclusions depended on it.
   - **Cause**: what the evidence shows, separated from what is inferred; label each inference.
   - **Fix**: the change to the skill, prompt, or environment that would stop it recurring.
   - **Severity**: `blocking` when the run's output cannot be trusted without rework, `degraded` when it stands with stated gaps, `minor` when the output is unaffected.

   Set the run status: `FAILED` when the run stopped before completing its work, `DEGRADED` when it completed with any deviation, `SUCCEEDED` only with no deviation. Completion: every deviation has impact, cause, fix, and severity, and the status follows these rules.

5. **Publish.** Write the report as a page and publish it with the host's Artifact tool, following that tool's instructions for authoring the page. The artifact stays private; sharing it is the user's choice. Title it with the run name and date. Sections, in order:
   - **Status** — the status, run name, start and end time, host, model ID, skills loaded and missing, and a one-line verdict on whether the outputs can be trusted.
   - **Outputs** — each output the run produced, with its URL, and the deviations it rests on.
   - **Problems** — blocking first, then degraded, then minor; each with where, what happened, what the run did instead, impact, cause, and fix.
   - **Unverified** — what this run could not confirm, and why.

   With no deviations, the Problems section reads `No problems: every step ran as written.` and the report still publishes. Completion: the artifact URL is recorded.

6. **Report.** End the run's final message with the status, the artifact URL, and a count of problems by severity. When the Artifact tool is unavailable or publishing fails, say so with its error, write the report to a Markdown file in the scratch directory, and put the full report in the final message instead. Completion: the final message carries the status and either the artifact URL or the full report.
