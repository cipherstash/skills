# CipherStash company skills

The language shared by the company skills, especially the Vanta remediation and triage workstreams and the run reports that unattended runs publish.

## Vanta tracking issues

**Tracking issue**:
A Linear issue in the AppSec project that stands for one group of Vanta findings: one package in one repo, or one OS package across the images built from one repo.
_Avoid_: Ticket, Vanta issue (ambiguous with the finding itself)

**Remediate issue**:
A tracking issue for a vulnerable dependency that has a fix version, titled `[Vanta] Remediate {package} to {versions} ({repo})`.
_Avoid_: Vuln issue, Dependabot issue

**AWS configuration issue**:
A Linear issue for a failing Vanta infrastructure test, such as database monitoring, titled `[Vanta] Remediate "{test name}"`. It is not a Remediate issue, even though its title starts the same way.
_Avoid_: Remediate issue

**Assess issue**:
A tracking issue for OS-package findings in container images, which needs a judgement on whether a fix exists and applies.
_Avoid_: Container issue

**Track-upstream issue**:
A tracking issue for a vulnerability with no fix available yet, waiting on the upstream project.

**Remediate queue**:
The Todo Remediate issues in the AppSec project that a scheduled remediation run works through, ordered by priority and then due date. A run asked to include assessments adds Todo Assess issues to it, in the same order.
_Avoid_: Backlog, Todo list

## Triage actions

**Refresh**:
Rewriting a tracking issue's generated section because the set of advisories Vanta reports for it has changed, or because a new image is affected. An image dropping out of Vanta's report is not a refresh.
_Avoid_: Update, sync

**Retarget**:
Changing a Remediate issue's fix version because Vanta raised it.

**Realign**:
Making a tracking issue's priority or due date stricter because it is less urgent than Vanta's severity or SLA. A realign never relaxes a value.
_Avoid_: Reprioritise, sync

**Resolve**:
Closing a tracking issue because Vanta no longer reports any of its findings.
_Avoid_: Close (too general)

**Reopen**:
Moving a recently resolved or Done tracking issue back to Todo because Vanta reports its findings again, instead of filing a new issue. A cancelled tracking issue is never reopened: cancelling is a human decision to accept the risk.
_Avoid_: Refile, recreate

## Run reports

**Deviation**:
Any point where an unattended run did not do what its prompt or a skill said, as written.
_Avoid_: Issue, problem (as a defined term), error

**Misstatement**:
A claim in a run's output that the run's own deviation log contradicts.

**Run date**:
The calendar date a run started, in the timezone its prompt names, or labelled as UTC when the prompt names none.

## Language skills

**Language skills**:
The set CipherStash ships for one programming language: a `<lang>-practices` skill, a `<lang>-review` skill, and the language's check suite. Say "the Python skills" or "the TypeScript skills".
_Avoid_: Pair, language pair, skill pair

**Check suite**:
The canonical set of checks that CI runs as a hard gate on every pull request, in every repository in one programming language. Each language has its own, such as the Go check suite. Every language's skills define one.
_Avoid_: Toolchain, the language's checks

**Untrusted input**:
Bytes that come from outside the process, such as a request body, a file, or a message. A function that parses or decodes untrusted input must have a fuzz target or a property test, whichever the language's check suite names, unless that suite says why neither fits. Go's is a Fuzz target.
_Avoid_: User input, external data

**In place**:
A check is in place when it is a GitHub Actions step that runs on `pull_request`, blocks when it fails, covers every module except fixtures with planted defects, and pins its version. Nothing may ignore its exit status: no `continue-on-error`, even when a later step enforces its result; no `|| true`; and no other way, such as a shell without `-e` or a pipe without `pipefail`. A path-filtered trigger counts only alongside a changes job that fails closed. A version is pinned when it is exact, or fixed by a committed lockfile that CI installs frozen or locked. The language runtime floats.
_Avoid_: Enabled, configured, present

**Execution surface**:
The files and flags through which a change runs its own code when a tool builds, lints, or tests it, such as Python's `conftest.py`, Rust's `build.rs`, or Go's `-toolexec`. Each language's skills list theirs. When a change touches its execution surface, an agent runs no tool that would run the change's code until the user says yes.
_Avoid_: Attack surface, hooks
