---
name: run-report
description: Keeps a log of every problem an unattended run hits — errors, failed commands, retries, fallbacks, workarounds, skipped or partial steps, missing skills or access, and assumptions made in place of instructions — then publishes a run report as a Claude artifact, or in the final message where artifacts are unavailable, with the run's status, an analysis of each problem, and its impact on what the run produced; a clean run still publishes one. Use when a scheduled task's or routine's prompt lists this skill or asks for a run report, or when asked to report what went wrong in a run. Does not diagnose a single failure, post review findings (review-post), or file issues (filing-github-issues).
argument-hint: "[run name]"
---

# run-report

Make every **deviation** visible. A deviation is any point where the run did not do what its prompt or a skill said, as written: a command that failed, a retry, a fallback route, a workaround, a step skipped or done in part, a value left `unknown` where no instruction allowed it, a gap filled by assumption. A run that patches over a deviation and carries on produces output that looks normal and is not; the report is where the patch shows.

This skill records; it changes nothing about how the run behaves except that an unanswerable approval gate becomes a stop. Follow every other skill's and the prompt's instructions as written, including each instruction to stop, and never continue past a stop to give the report more to say. Treat the run as unattended when a schedule or routine started it or its prompt says so; otherwise someone can answer, and the run asks as its skills say. An instruction to ask, or to get an approval the prompt or skill has not already granted, is a stop when no one can answer: do not take the action, and never treat silence as consent. The report still publishes after any stop. The skill proposes fixes and never makes them: it does not edit skills, prompts, or the environment, or file issues.

Every run publishes one report. A missing report means the run died before the end.

## Inputs

- The run's prompt and the skills it loaded: the instructions deviations are measured against.
- A run name, if given; otherwise derive one from the prompt and its target, such as `Code review PR 1496`; when the prompt names no task or target, `Unnamed run <date>`. Never ask: an unattended run has no one to answer.

## Steps

1. **Open the log.** Create the log at `run-report/<slug>-<start>.log.md`, where the slug is the run name in lowercase ASCII letters and digits with every other run of characters replaced by a single hyphen and no leading or trailing hyphen, and `<start>` is the run's start time as `YYYYMMDD-HHMMSS` — or, when this skill loaded late and the start is unknown, the load time, noted as such. Put the `run-report/` directory in the session's scratch directory, or, on a host without one, in the system temp directory (`$TMPDIR`, else `/tmp`); never inside a repository. Never write to another run's log. State the full log path and the run's start time in the session once the log exists, so a compaction summary keeps them. Record in the log's header the run name, start time, host product (such as Claude Code or Codex), model ID, the session ID when the host exposes one, and the prompt's skills, each marked loaded or missing. A missing skill is the first deviation. When this skill was loaded after the run's work began, still create the log now and note the late load in it. After context compaction, keep appending to the log path the summary kept; when the summary lost it, search every `*.log.md` in that directory for the header that matches this session's ID or this run's start time as the summary kept it. The run name, host product, model ID, and skills repeat across scheduled runs, so never match on them alone: when neither the session ID nor the start time survived, when no file matches, or when more than one could, start a new log with the restart time as `<start>` rather than guess, and log the loss as a deviation. Completion: the log file exists at that path.

2. **Log as you go.** Continue the run's own work. The moment a deviation happens, append an entry to the log before doing anything else — the log is on disk so it survives context compaction:
   - **Where**: the skill and step, or the prompt line, whose instruction was not followed as written.
   - **What happened**: the command or tool call and its exact error, exit code, or output, quoted. Quote only the lines that show the problem. Redact tokens, secrets, and credentials, and summarise rather than quote file contents, customer data, and internal hostnames.
   - **What the run did instead**: the retry, alternate command or API, manual step, assumption, or skip. When an instruction said to stop and the run continued anyway, say so; that is itself a deviation.

   A non-zero exit or warning the instruction anticipates — `grep` finding nothing, a check whose failure is a planned branch — is not a deviation.

   When the run stops — obeying a stop instruction or an unanswerable approval gate — append an entry for the stop with the same fields, even though obeying it is not a deviation. When the run produces an output — a posted review, a comment, a PR, an issue — append its kind and URL to the log, with any claim it makes about which skills or steps ran. When the run's work ends, append the end time. Completion, checked when the run's work ends: every output is in the log, and every unanticipated non-zero exit, tool error, retry, and alternate route still visible in the session has an entry.

3. **Reconcile.** Read back through the session as far as it is still visible — or, when this skill was loaded late, build the log from it now. Hunt for deviations the log missed:
   - unanticipated non-zero exits and tool errors, including ones a later call succeeded past;
   - retries and timeouts;
   - fallbacks: a different command, API, endpoint, or tool than the one written;
   - steps skipped, partly done, or done out of order;
   - data read in part: truncated output, an unread page, a file too large to read;
   - values reported `unknown` where no instruction allowed it, or guessed;
   - instructions that were ambiguous, contradictory, or impossible here, and the reading the run chose — unless an instruction said to ask, which makes it a stop;
   - missing skills, tools, permissions, credentials, or network access;
   - warnings the run noted and moved past that bear on an output.

   When context was compacted, or the skill was loaded late, the earlier part of the session can be checked only through the log or not at all: record that in **Unverified** rather than claim a full reconciliation.

   Then check each output the log lists, and any the visible session shows that the log missed, against the log's deviations. A claim in an output that the log contradicts — a skill or step named as used while the log shows it bypassed or degraded, tests reported passing that failed, feedback reported fully checked that was read in part — is a **misstatement**: add a deviation naming the output's URL and what it claims. Only read the outputs; do not edit, retract, or comment on them. An output that cannot be read goes in **Unverified**. Completion: every item above was checked against the visible session, any gap is recorded as unverified, and every output was compared with the log.

4. **Analyse.** For each deviation, add:
   - **Impact**: which outputs, findings, or claims rest on it, and what is now unverified or wrong. A fallback that fetched less data than the written route says which data, and which conclusions depended on it.
   - **Cause**: what the evidence shows, separated from what is inferred; label each inference.
   - **Fix**: the change to the skill, prompt, or environment that would stop it recurring, proposed only.
   - **Severity**: `blocking` when the run's output cannot be trusted without rework, `degraded` when it stands with stated gaps, `minor` when the output is unaffected. Continuing past a stop or an unanswered approval gate is always `blocking`.

   Set the run status: `FAILED` when the run stopped before completing its work — on an error, a missing prerequisite, or an approval no one could give. A stop the instructions name as the nothing-to-do outcome, such as "nothing to commit, stop and say so", completes the work and is not a failure; a stop caused by an error, a missing prerequisite, or an unanswered approval never qualifies, even when the instructions name it. Otherwise `DEGRADED` when the run completed with any deviation — even a single `minor` one, and even a `blocking` one, which the verdict line then flags as untrusted — and `SUCCEEDED` only with no deviation. A `FAILED` run's stop is always logged and reported as a `blocking` problem with impact, cause, and fix, even when the run obeyed it, so a failed report never reads `No problems`. Completion: every deviation has impact, cause, fix, and severity, and the status follows these rules.

5. **Publish.** Write the report as a page and publish it with the host's Artifact tool, following that tool's instructions for authoring the page. The artifact stays private; sharing it is the user's choice. Title it with the run name and date. Sections, in order:
   - **Status** — the status, run name, start and end time, host product, model ID, skills loaded and missing, and a one-line verdict on whether the outputs can be trusted.
   - **Outputs** — each output the run produced, with its URL, and the deviations it rests on.
   - **Problems** — blocking first, then degraded, then minor; each with where, what happened, what the run did instead, impact, cause, and fix.
   - **Unverified** — what this run could not confirm, and why.

   With no deviations, the Problems section reads `No problems: every step ran as written.` and the report still publishes. Step 2's redaction rule applies to every copy of the report: the artifact, the fallback file, and the final message; output URLs are exempt, since the reader needs them. When the Artifact tool is unavailable or publishing fails, record its error, write the report to `<slug>-<start>.report.md` beside the log, and carry the full report in the final message instead. Completion: the artifact URL is recorded, or the publishing error and the report file are.

6. **Report.** End the run's final message with the status, the artifact URL, and a count of problems by severity — or, when publishing failed, the error and the full report. Completion: the final message carries the status and either the artifact URL or the full report.
