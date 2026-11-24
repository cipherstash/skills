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

## Language skill checks

**Go check suite**:
The checks every Go repository runs in CI on each pull request: format, lint, known vulnerabilities, pattern scan, race-enabled tests, and a coverage report. CI runs them; agents do not. Profiling and benchmarks are not part of it.
_Avoid_: Go toolchain (Go uses that for the compiler release), linters (too narrow)

**In place**:
Said of a check in the suite: a blocking, version-pinned CI step that runs on every pull request and covers every Go module, or a check that an exemption covers.
_Avoid_: Configured, enabled

**Exemption**:
An ADR on the default branch, approved through an issue and a merged pull request, that excuses a repository from named checks in the suite and says why.
_Avoid_: Waiver, skip

**Repository standards**:
The part of a review that checks the repository's CI against the suite, reported apart from findings about the change itself.
_Avoid_: Standards (alone: the code-review skill's Standards axis means coding standards)
