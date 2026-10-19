---
name: vanta-triage
description: Check Vanta for open vulnerability findings (Dependabot package alerts and AWS Inspector container findings), group them by repo and package, and reconcile them against the Linear AppSec tracking issues — filing issues for new findings, retargeting issues when Vanta raises the fix version, and closing issues whose findings Vanta no longer reports. Use when asked to check Vanta, look for new security alerts or vulnerabilities, sync Vanta with Linear, file Vanta issues, or run the scheduled Vanta triage, including unattended routine runs. Does not patch repositories or open PRs (vanta-remediate does that).
argument-hint: "[dry run] [severity or repo filter]"
---

# vanta-triage

Vanta is the source of truth for what is vulnerable; Linear is where the work is tracked. Each run makes Linear match Vanta: one open issue per `(repo, package)` or `(image, package)` that Vanta reports, at the fix version Vanta requires, and no open issue for anything Vanta has stopped reporting.

The run is unattended-safe: it never asks a question mid-run. Where judgement is needed, it takes the conservative action below and says so in the report.

## Inputs

- **Mode.** Apply by default. A request for a dry run, preview, plan, or "what would change" makes no Linear writes: run steps 1–4 and report the actions as planned.
- **Filter** (optional): a severity floor or a repo/image. Apply it to the plan's groups and actions before step 5; never resolve issues outside the filter.
- **Configuration**: [references/config.json](references/config.json) names the Linear team, project and assignee, and maps container images to the repos that build them. Edit it, not this file, when those change.

Credentials: either a Claude Code environment network secret of type OAuth 2.0 client credentials for `api.vanta.com` (token URL `https://api.vanta.com/oauth/token`, scope `vanta-api.all:read`), which adds the token to each request so the session never holds the secret; or `VANTA_CLIENT_ID` and `VANTA_CLIENT_SECRET` (or `VANTA_ENV_FILE` pointing at a JSON file with `client_id` and `client_secret`). With neither variable set, the script sends requests without an Authorization header and relies on the network secret. Either way it needs network access to `api.vanta.com`. Linear access is through the Linear connector's tools (`list_issues`, `save_issue`, `save_comment`).

## Steps

Work in a scratch directory. Resolve scripts from this skill's directory, not the working directory.

1. **Fetch findings.** `python3 <skill dir>/scripts/vanta.py fetch --out <scratch>/findings.json`. A non-zero exit stops the run: report the error verbatim (it names the missing credential, HTTP status, or blocked host). Completion: the findings file exists; note the count.

2. **Fetch Linear issues.** Call `list_issues` once per state type: `triage`, `backlog`, `unstarted`, `started`, and `completed` with `updatedAt: "-P14D"`. Pass `project` from the config, `limit: 250`, and `fields: ["id", "title", "status", "statusType", "completedAt"]` each time. Leave out descriptions: list results truncate them, and titles carry what matching needs, and follow `cursor` until `hasNextPage` is false. Don't pass `query`: the connector's text search returns a partial result set without saying so, and an issue missing from the list gets filed again as a duplicate. Save each response to its own file under `<scratch>/issues/`, as returned. A result too large to show inline is already saved to a file by the host; use that path. The script reads every file and ignores non-`[Vanta]` titles. A connector failure stops the run. Completion: every state type and page saved.

3. **Plan.** `python3 <skill dir>/scripts/vanta.py plan --findings <scratch>/findings.json --issues <scratch>/issues/* > <scratch>/plan.json`. Its docstring defines the output. Completion: `plan.json` parsed.

4. **Check the plan** before writing anything:
   - **Mass resolve guard.** The plan applies it: if `resolve` actions would exceed 5 and exceed half the open package issues, or the fetch returned zero findings while open issues exist, it emits each as a `guard` action instead and sets the top-level `guard` to the reason — a partial Vanta response looks exactly like everything being fixed. Resolve nothing this run; report the guard tripping with `guard`.
   - **Duplicates.** A group with `duplicates` has more than one open issue for the same thing; its `match` is kept. An extra issue whose title fits several groups is listed under the first of them.
   - **Fetch until settled.** An action with `fetch_description` names an issue whose description the plan has not seen whole (list results may truncate it before the `Vanta key:` line), so it cannot tell whether the generated section is current. An action with `ambiguous` matched its issue by title alone, and the title also fits other groups (the same package in two ecosystems of one repo, or two repos with the same name); the description's `Vanta key:` line settles which group owns it. Call `get_issue` for each such issue not fetched yet this run, save each result to `<scratch>/issues/<id>.json` as returned, and rerun step 3. Repeat until no action names an unfetched issue: a fetched description can move an issue to another group and hand its group an issue the plan has not seen. Each issue is fetched at most once, so this ends. An ambiguous issue with no key line keeps the plan's choice and is listed in the report.
   - **Umbrella issues.** An `unparsed` open issue that names a container image (for example `[Vanta] Rebuild zerokms ECR image — …`) predates per-package tracking. New container issues for that image are still created, but link to it (`relatedTo`).
   - **Stale "no fix".** Vanta's fixed version comes from the advisory, which often lags the registry. For each `track-upstream` group, check the registry for a release outside every advisory's affected range: `npm view <pkg> versions --json`, `cargo info <pkg>`, `go list -m -versions <module>`, or `pip index versions <pkg>`. If one exists, treat the group as remediate at the lowest such version. The plan never retitles a Remediate issue whose group lost every fix, only refreshes its table, so this override is not undone on the next run. Retarget a matched issue (or file a new one) titled `[Vanta] Remediate <pkg> to <version> (<repo>)`, and cite the release in the comment. A release that is only newer, with no advisory range or changelog showing the fix, is not enough.
   - Container groups whose `repo` is null name an image missing from the config's `images` map: create the issue anyway and list the image in the report so the map can be updated. Once it is mapped, the next plan refreshes that issue to the repo's key rather than resolving it.

5. **Apply** (skip in dry-run mode). Act on each action; one failed call is reported and the run continues.
   - **create** — `save_issue` with `team`, `project`, and `assignee` from the config, the group's `title`, `description`, and `priority`, `dueDate` set to the group's `sla`, and `state: "Todo"`.
   - **retarget** — `save_issue` with the new `title` and `patch` set to the action's `patch`, verbatim; then `save_comment` with the `reason`. The patch replaces only the generated section (the first `## Vulnerability` through the first `Vanta key:` line after it), or prepends one above an issue filed before this format; human text outside it stays. The section ends with a fenced `json` advisory block, which is what vanta-remediate reads (the table is for people), and its `Advisory set:` digest seals that block: an edited block is refused until the next refresh. Never edit the section by hand. If the issue was **In Review**, move it to **Todo** and say in the comment that the linked PR does not reach the new version. A retarget or refresh without `patch` (its fetch failed) is reported as failed, not written by hand.
   - **refresh** — `save_issue` with `patch` set to the action's `patch`, verbatim, and the title unchanged; then `save_comment` with the `reason`. Vanta added or dropped an advisory, or (for a container) an affected image, without moving the target. A new advisory with no fix needs vanta-remediate's residual check, and it only runs that check for advisories in the block. An issue filed before the advisory block carries an older digest, so it is refreshed once. A title whose targets over-cover after a refresh (Vanta dropped the advisory behind its higher target) is left alone: remediation then judges against the higher target alone, which errs on the safe side. Container titles may carry a human verdict such as "not affected", which is why refresh never retitles.
   - **resolve** — `get_issue` with `attachments` first. Then `save_issue` with `state: "Done"` and a `save_comment` saying Vanta no longer reports an active finding for it as of today's run, naming any linked PR. Vanta is the evidence here, not the PR: a finding can clear through Dependabot or another change.
   - **duplicates** — `save_issue` with `duplicateOf` set to the kept issue, and a comment saying so.
   - **keep**, **await-rescan**, **guard** — no write.

   Completion: every action applied or recorded as failed.

6. **Report.** Lead with counts by action. Then one line per create, retarget, refresh, and resolve: issue id and link, title, severity, SLA. Then await-rescan items, unparsed open issues, guard trips, config gaps, and any failed writes with the error. In dry-run mode, say plainly that nothing was written. Name `vanta-remediate` as the next step for Todo `Remediate` issues.

## Conventions

- Titles drive matching for issues that predate the `Vanta key:` line in descriptions, so keep the shapes the script renders: `[Vanta] Remediate {package} to {versions} ({repo})`, `[Vanta] Track upstream fix for {package} ({repo})`, `[Vanta] Assess {package} {advisories} ({image} image)`, with every affected image listed when several images are built from one repo: `(zerokms + cts images)`. Versions on different major lines are joined with ` / `.
- Severity maps to Linear priority: Critical 1, High 2, Medium 3, Low 4. The due date is Vanta's SLA date.
- Never delete issues, edit issues outside the configured project, or touch Linear issues that are not `[Vanta]` package or container issues (AWS configuration findings such as "SQL database CPU monitored" are out of scope).
