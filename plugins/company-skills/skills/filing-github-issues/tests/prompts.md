# Behavior cases

## Should activate

- "File a GitHub issue on cipherstash/stack: `stash eql upgrade` drops our search indexes."
- "Can you write this bug up for the encrypt-query-language repo so the team can pick it up?"
- "Draft an issue for the problem we just found."
- "Open an issue about this" with no repo given and none inferable from the session — the skill asks which repository, and what the problem is if that is unclear.

## Should not activate

- "Open a PR for this fix" — authoring-pull-requests.
- "Create a Linear ticket for this bug" — Linear, not GitHub.
- "What review feedback is still outstanding on PR 42?" — audit-pr-feedback.
- "Patch the Vanta findings in CIP-1234" — vanta-remediate.

## Expected behavior

- Before drafting, searches open and closed issues in the target repo and each plausible sibling repo with `search_issues`, and lists the repos and queries searched.
- A closed issue covering the problem is read to find why it closed, and the user is offered a reopen or comment instead of a duplicate; an open duplicate stops the filing.
- Every mechanical claim cites `file:line` or a command and its output; inferred claims are marked plausible, never presented as verified.
- An upstream cause is filed upstream; a consumer-repo issue is added only when that repo needs its own mitigation; cross-references use `owner/repo#N`.
- The body has Background, Problem, Proposal in that order; optional sections appear only when they add something.
- Wording: acronyms expanded at first use, symptom-first title naming the command or package, no `#N` except real issue or PR references, no `CIP-` Linear numbers anywhere.
- Labels are taken from labels already in use and confirmed with `get_label`; none are invented.
- The draft (repo, title, labels, body, planned back-link comments) is shown first; `issue_write` runs only when the user asked to file or approves.
- After filing, a back-link comment is posted on each related issue, and the report gives the new issue's URL.
- Uses GitHub MCP tools; the `gh` CLI only when the MCP server is unavailable, and the report says so.
