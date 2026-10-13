# Behavior cases

`test_vanta.py` covers `scripts/vanta.py` (parsing, grouping, version ordering, Linear reconciliation) without network access: `python3 -m unittest discover -s tests` from the skill directory.

## Should activate

- `/vanta-triage` from a scheduled routine with no further instructions.
- "Check Vanta for any new security alerts and make sure Linear is up to date."
- "Are there new Dependabot findings in Vanta we haven't filed yet? Just tell me, don't create anything." (dry run)
- "Sync Vanta with Linear for stack only."
- "Run the Vanta triage" when `VANTA_CLIENT_ID` is unset: the run stops at step 1 and reports which credential is missing, without asking.

## Should not activate

- "Patch CIP-4892" or "open PRs for the Todo Vanta issues" — vanta-remediate.
- "Remediate the 'SQL database CPU monitored' Vanta test" — an AWS configuration test, not a vulnerability finding.
- "Review this PR's Dependabot bump" — a code review.

## Expected behavior

- Findings come from `scripts/vanta.py fetch`; a non-zero exit stops the run with the script's error, and nothing is written to Linear.
- Linear issues are listed from the configured project with every page followed, and saved verbatim for `plan`.
- Each `create` uses the plan's title, description, priority, and the SLA as due date, with the configured team, project, and assignee, in Todo.
- Multiple Dependabot alerts for one package in one repo become one issue; fix versions on different major lines appear joined with ` / `.
- A package with no fixed version gets a `Track upstream fix` issue; one that later gains a fix is retargeted to `Remediate … to …`, not duplicated.
- A retarget updates the title and adds a comment without overwriting the description; an In Review issue being retargeted moves to Todo with the PR's shortfall noted.
- A `resolve` closes the issue as Done with a comment citing Vanta's absence of the finding; the mass-resolve guard blocks all resolves when the fetch looks partial.
- A finding matching an issue closed in the last 7 days with a covering version is reported as awaiting rescan, not refiled.
- Container findings group per image and package, link any legacy umbrella issue for the image, and name images missing from the config map.
- Unparsed `[Vanta]` issues (AWS configuration findings, legacy umbrellas) are listed and never edited or closed.
- Dry-run mode performs no Linear writes and says so.
- The run never stops to ask a question.
