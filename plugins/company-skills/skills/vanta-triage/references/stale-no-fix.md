# Stale "no fix" check

Read this in step 4 for each `track-upstream` group whose action is `create`, `keep`, `refresh`, `reopen`, `canceled`, or `await-rescan`.

Vanta's fixed version comes from the advisory, which often lags the registry. A package Vanta reports as unfixed may already have a fixing release.

## Check the registry

List the package's published versions:

- npm: `npm view <pkg> versions --json`
- Cargo: `cargo info <pkg>`
- Go: `go list -m -versions <module>`
- PyPI: `pip index versions <pkg>`

Look for a release outside every advisory's affected range. A release that is only newer, with no advisory range or changelog showing the fix, is not enough: leave the group as track-upstream.

If the registry cannot be queried (no network, the tool is missing) or the ecosystem is not listed above, leave the group as track-upstream and list it in the report as unchecked.

## When a fixing release exists

Treat the group as remediate at the lowest such version, titled `[Vanta] Remediate <pkg> to <version> (<repo>)`. Never edit the generated section by hand: the advisory block keeps the advisory's missing fix until Vanta catches up, and vanta-remediate adds a fix check for the title's target when the title and block differ.

When the matched issue's title already names `Remediate` at this version or higher, make no override write: an earlier run made it, and repeating it would only add a comment. A `refresh` action's own write still applies.

- **create**: `save_issue` as SKILL.md step 5 says, with the plan's `description`, `priority`, and `sla`, but the Remediate title.
- **keep**: `save_issue` with only the new title, then `save_comment` citing the release.
- **refresh**: `save_issue` with the new title and the action's `patch`, verbatim, then `save_comment` with the action's `reason` and the release.
- **reopen**: the reopen as SKILL.md step 5 says, but with the Remediate title, and the release cited in the comment. Never file a new issue for it.
- **canceled** or **await-rescan**: the entire group is report-only, even when an open duplicate supplies a `match`. Suppress every write for that group, and report the release beside the cancelled or closed issue instead.

The override persists: the plan never retitles a Remediate issue whose group lost every fix, it only refreshes the table, so the next run does not undo the retarget.
