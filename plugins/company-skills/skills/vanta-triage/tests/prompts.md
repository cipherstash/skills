# Behavior cases

`test_vanta.py` covers `scripts/vanta.py` (parsing, grouping, version ordering, Linear reconciliation) without network access, and `test_workflow.py` runs SKILL.md's loop end to end against a fake Linear store: `python3 -m unittest discover -s tests` from the skill directory.

## Should activate

- `/vanta-triage` from a scheduled routine with no further instructions.
- "Check Vanta for any new security alerts and make sure Linear is up to date."
- "Are there new Dependabot findings in Vanta we haven't filed yet? Just tell me, don't create anything." (dry run)
- "Sync Vanta with Linear for stack only."
- "Run the Vanta triage" when only one of `VANTA_CLIENT_ID` and `VANTA_CLIENT_SECRET` is set: the run stops at step 1 and reports which credential is missing, without asking.
- "Run the Vanta triage" when neither is set and no network secret covers `api.vanta.com`: step 1 stops on the HTTP 401 and the error asks whether a network secret is configured.

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
- A retarget updates the title and replaces only the generated vulnerability section of the description (from `## Vulnerability` to the `Vanta key:` line), keeping human notes, and adds a comment; an In Review issue being retargeted moves to Todo with the PR's shortfall noted.
- When Vanta adds or drops an advisory but the fix target is unchanged (for example, a new advisory with no fix affecting `< 2.0.0` on an issue targeting 1.2.2), the issue is refreshed: its vulnerability section is replaced, so the table includes the new row and its `Advisory set:` digest is updated. Its title stays. A tracked issue the plan saw without a description is fetched with `get_issue` before the plan is rerun, and fetching repeats until no action names an unfetched issue.
- Every description write passes the plan's `patch` verbatim; an issue filed before this format gets the generated section prepended once, and later refreshes replace only that section.
- A container finding that gains an advisory or spreads to another image refreshes the issue's table and `**Images:**` line; its title, including any "not affected" verdict, stays.
- A Remediate issue whose group loses every fix, or whose title names a higher target Vanta no longer requires, is refreshed with its title unchanged.
- A `resolve` closes the issue as Done with a comment citing Vanta's absence of the finding; the mass-resolve guard blocks all resolves when the fetch looks partial.
- A finding matching an issue closed in the last 7 days with a covering version and the same `Advisory set:` digest is reported as awaiting rescan, not refiled; a new advisory on that package is filed.
- A finding whose issue was closed as Done 3 to 14 days ago, matched by its `Vanta key:` line, reopens that issue: it moves to Todo, its generated section is refreshed when its advisories changed, and a comment gives the close date and that Vanta reports the finding again. No new issue is filed. For example, CIP-5292 (minimatch, stack), resolved on 4 Nov while main was still vulnerable, is reopened rather than duplicated as CIP-5331. A match closed more than 14 days ago is filed as a new issue, and a closed issue with no key line is never reopened by title alone. The report lists reopens beside creates, retargets, refreshes, and resolves. Covered by `test_vanta.py` (`Reopen`) and `test_workflow.py`.
- Container findings group per image and package, link any legacy umbrella issue for the image, and name images missing from the config map.
- Each open issue serves at most one group; when a title fits several groups (npm and Rust `tar` in one repo), the issue's `Vanta key:` line is fetched to settle it rather than retargeting the issue back and forth.
- Issues in custom open states (for example "Blocked") count as open.
- A finding matching an issue cancelled in the last 14 days, by its `Vanta key:` line, is listed in the report naming the cancelled issue. Nothing is written: no new issue, no reopen, no comment, because cancelling is a human decision to accept the risk. A cancellation older than 14 days, or an issue marked Duplicate, does not count, and the finding is filed as usual. Covered by `test_vanta.py` (`CanceledMatch`) and `test_workflow.py`.
- An advisory that spans several version lines appears once per affected range in the description table; package names keep their spelling in the `Vanta key:` line.
- The generated section carries a fenced `json` advisory block with every advisory's id, raw affected range (including `||`), and fixed version or null; the table escapes `|` and is for people only. Covered by vanta-remediate's `test_contract.py`.
- The same Linear issue seen once by uuid and once by its `CIP-` identifier (a list page keyed by `id` = uuid, a `get_issue` result with both) is one issue, never its own duplicate; every id the plan emits is the `CIP-` identifier. Covered by `test_vanta.py` (`SixthReview`).
- A run that has only summarised Linear data (a hand-built array of ids and titles, or issues missing `statusType`) gets exit 2 from `plan` naming the file. It refetches with `list_issues` and saves the responses as returned; it never edits the data to pass the check, and never edits a description by hand. Covered by `test_vanta.py` (`RawConnectorInput`), with fixtures in `tests/fixtures/` that keep a real connector response's shape.
- Unparsed `[Vanta]` issues (AWS configuration findings, legacy umbrellas) are listed and never edited or closed.
- Dry-run mode performs no Linear writes and says so.
- The run never stops to ask a question.
