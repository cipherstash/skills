# CipherStash company skills

The language shared by the company skills, especially the Vanta remediation and triage workstreams and the run reports that unattended runs publish.

## CipherStash services

**CipherStash service**:
A service that CipherStash builds and runs for customers, such as CTS or ZeroKMS. A Lambda function that supports a CipherStash service is not a CipherStash service.
_Avoid_: Service (alone, when an AWS service could be meant)

**CipherStash Token Service (CTS)**:
The CipherStash service that authenticates clients and issues the service tokens that other CipherStash services accept.

**Service token issued by CTS**:
The bearer token a client sends with each request to a CipherStash service, such as ZeroKMS. It lists the permissions that CTS granted to the client.
_Avoid_: CipherStash Service Token, CST, CTS token (each is too close to "CTS")

**Token exchange**:
The step where a client gives CTS an access key or a token from another identity provider, and CTS returns a service token.

**Feature permission**:
A permission that CTS adds to a service token at token exchange. It lets the client use one feature, such as the MCP interface. The service that offers the feature checks for it in the token.
_Avoid_: Feature flag, allow list

**Control plane endpoint**:
The part of a CipherStash service's API that creates, reads, updates, or deletes the service's resources, such as workspaces or keysets. Each service has its own. If the control plane is ever split from the rest of the API, the split stays inside that service.
_Avoid_: Control plane service (no separate service exists or is planned)

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

**Check suite**:
The canonical set of checks that gate every pull request, run in CI, in every repository in one programming language. Each language has its own, such as the Go check suite. Every language skill pair defines one.
_Avoid_: Toolchain, the language's checks

**Untrusted input**:
Bytes that come from outside the process, such as a request body, a file, or a message. A function that parses or decodes untrusted input must have a Fuzz target.
_Avoid_: User input, external data
