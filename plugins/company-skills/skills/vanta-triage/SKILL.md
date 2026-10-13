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

Credentials: `VANTA_CLIENT_ID` and `VANTA_CLIENT_SECRET` (or `VANTA_ENV_FILE` pointing at a JSON file with `client_id` and `client_secret`), and network access to `api.vanta.com`. Linear access is through the Linear connector's tools (`list_issues`, `save_issue`, `save_comment`).

## Steps

Work in a scratch directory. Resolve scripts from this skill's directory, not the working directory.

1. **Fetch findings.** `python3 <skill dir>/scripts/vanta.py fetch --out <scratch>/findings.json`. A non-zero exit stops the run: report the error verbatim (it names the missing credential, HTTP status, or blocked host). Completion: the findings file exists; note the count.

2. **Fetch Linear issues.** Call `list_issues` once per state type: `triage`, `backlog`, `unstarted`, `started`, and `completed` with `updatedAt: "-P14D"`. Pass `project` from the config, `limit: 250`, and `fields: ["id", "title", "status", "statusType", "completedAt"]` each time. Leave out descriptions: list results truncate them, and titles carry what matching needs, and follow `cursor` until `hasNextPage` is false. Don't pass `query`: the connector's text search returns a partial result set without saying so, and an issue missing from the list gets filed again as a duplicate. Save each response to its own file under `<scratch>/issues/`, as returned. A result too large to show inline is already saved to a file by the host; use that path. The script reads every file and ignores non-`[Vanta]` titles. A connector failure stops the run. Completion: every state type and page saved.

3. **Plan.** `python3 <skill dir>/scripts/vanta.py plan --findings <scratch>/findings.json --issues <scratch>/issues/* > <scratch>/plan.json`. Its docstring defines the output. Completion: `plan.json` parsed.

4. **Check the plan** before writing anything:
   - **Mass resolve guard.** If `resolve` actions exceed 5 and exceed half the open package issues, or the fetch returned zero findings while open issues exist, do not resolve anything this run — a partial Vanta response looks exactly like everything being fixed. Report the guard tripping.
   - **Duplicates.** A group with `duplicates` has more than one open issue for the same thing; the first is kept.
   - **Ambiguous matches.** An action with `ambiguous` matched its issue by title alone, and the title also fits other groups (the same package in two ecosystems of one repo, or two repos with the same name). Call `get_issue` for that issue, save the result to `<scratch>/issues/`, and rerun step 3: the description's `Vanta key:` line settles which group owns it. If it has no key line, keep the plan's choice and list the issue in the report.
   - **Umbrella issues.** An `unparsed` open issue that names a container image (for example `[Vanta] Rebuild zerokms ECR image — …`) predates per-package tracking. New container issues for that image are still created, but link to it (`relatedTo`).
   - **Stale "no fix".** Vanta's fixed version comes from the advisory, which often lags the registry. For each `track-upstream` group, check the registry for a release outside every advisory's affected range: `npm view <pkg> versions --json`, `cargo info <pkg>`, `go list -m -versions <module>`, or `pip index versions <pkg>`. If one exists, treat the group as remediate at the lowest such version. Retarget a matched issue (or file a new one) titled `[Vanta] Remediate <pkg> to <version> (<repo>)`, and cite the release in the comment. A release that is only newer, with no advisory range or changelog showing the fix, is not enough.
   - **Images not yet named.** A `keep` whose reason says the issue title does not name some images means the finding has spread to another image. Add a comment listing the newly affected images and their advisories. Don't retitle: the title may carry a human verdict such as "not affected".
   - Container groups whose `repo` is null name an image missing from the config's `images` map: create the issue anyway and list the image in the report so the map can be updated.

5. **Apply** (skip in dry-run mode). Act on each action; one failed call is reported and the run continues.
   - **create** — `save_issue` with `team`, `project`, and `assignee` from the config, the group's `title`, `description`, and `priority`, `dueDate` set to the group's `sla`, and `state: "Todo"`.
   - **retarget** — `get_issue` for the current description, then `save_issue` with the new `title` and the group's vulnerability section swapped in. vanta-remediate reads its affected ranges from the description, so a stale table would let it pass a version the new target rejects.
     - If the description has a `## Vulnerability` heading and a `Vanta key:` line, use `patch: [{op: "replace_range", from: "## Vulnerability", to: "Vanta key:", new_string: <the group's description, cut just before its own "Vanta key:" line>}]`. Text above the heading and after the key line is human notes and stays.
     - Otherwise (an issue filed before this format), use `patch: [{op: "prepend", text: <the group's description> + "\n\n---\n\n"}]`, which keeps the old text below the rule.
     - Then `save_comment` with the `reason`.
     - If the issue was **In Review**, move it to **Todo** and say in the comment that the linked PR does not reach the new version.
   - **resolve** — `get_issue` with `attachments` first. Then `save_issue` with `state: "Done"` and a `save_comment` saying Vanta no longer reports an active finding for it as of today's run, naming any linked PR. Vanta is the evidence here, not the PR: a finding can clear through Dependabot or another change.
   - **duplicates** — `save_issue` with `duplicateOf` set to the kept issue, and a comment saying so.
   - **keep**, **await-rescan** — no write.

   Completion: every action applied or recorded as failed.

6. **Report.** Lead with counts by action. Then one line per create, retarget, and resolve: issue id and link, title, severity, SLA. Then await-rescan items, unparsed open issues, guard trips, config gaps, and any failed writes with the error. In dry-run mode, say plainly that nothing was written. Name `vanta-remediate` as the next step for Todo `Remediate` issues.

## Conventions

- Titles drive matching for issues that predate the `Vanta key:` line in descriptions, so keep the shapes the script renders: `[Vanta] Remediate {package} to {versions} ({repo})`, `[Vanta] Track upstream fix for {package} ({repo})`, `[Vanta] Assess {package} {advisories} ({image} image)`, with every affected image listed when several images are built from one repo: `(zerokms + cts images)`. Versions on different major lines are joined with ` / `.
- Severity maps to Linear priority: Critical 1, High 2, Medium 3, Low 4. The due date is Vanta's SLA date.
- Never delete issues, edit issues outside the configured project, or touch Linear issues that are not `[Vanta]` package or container issues (AWS configuration findings such as "SQL database CPU monitored" are out of scope).
