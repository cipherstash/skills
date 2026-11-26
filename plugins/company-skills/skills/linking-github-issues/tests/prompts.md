# Behavior cases

## Should activate

- "Link PR #212 to issue #140." The pull request targets a branch that is not the default.
- "Make #40 a sub-issue of #12."
- "Mark #88 as blocked by #77."
- "Add a relates-to link between #5 and #9."
- "#61 is a duplicate of #42. Close it and link them."
- "Create a branch for issue #30 and link it."
- "My PR against `next` says `Closes #18`, but the issue doesn't show it. Fix that."
- "Can GitHub link these two pull requests?" The agent checks the schema before it answers.
- An agent is about to tell the person that GitHub has no "relates to" link. The agent loads this skill and checks first.
- "Link these issues" with no kind of link named. The agent asks which link the person wants: relates to, blocked by, or sub-issue.

## Should not activate

- "File an issue for this bug." That is filing-github-issues.
- "Open a PR for this fix." That is authoring-pull-requests. That skill points here only if the base branch is not the default.
- "Stack these three branches." That is stacking-pull-requests.
- "Link CIP-123 to this Linear project." Linear is not GitHub. The agent does not open this skill.

## Expected behavior

- The agent makes each link with its GraphQL mutation. The agent never writes a `#NN` mention in place of a link the person asked for.
- For a pull request whose base is not the default branch, the agent compares the base with the default branch. The agent links the pull request with `addCloseIssueReferences`. The agent then reads it back from `closingIssuesReferences` or `closedByPullRequestsReferences`.
- The agent writes each query to a file in a temporary directory and runs `gh api graphql -F query=@<file>`, with variables as `-f name=value`.
- The agent looks up node ids first, with one aliased query where it can.
- The agent takes bare numbers from the current repository. The agent never uses `cipherstash/stack` or another repository from the skill's worked example.
- Given "Link these issues", the agent asks which kind of link and waits. The agent does not assume "relates to".
- After every mutation, the agent reads the link back in a separate query and reports what it showed.
- For a mutation other than `addRelatesTo` and `addCloseIssueReferences`, the agent tells the person that the skill had not seen it run before.
- Asked to relate an issue to a pull request, or two pull requests, the agent says that "relates to" links two issues only. For two pull requests, it offers a comment on the pull request that waits.
- For "blocked by", `issueId` is the issue that waits. `blockingIssueId` is the issue it waits for.
- To mark a duplicate, the agent closes the issue with `stateReason: DUPLICATE` and `duplicateIssueId` only when the person asked for it to be closed. Otherwise the agent explains that marking a duplicate closes the issue, and asks.
- The agent does not say that a linked pull request will close the issue on merge, unless it checked the auto-close setting and base branch.
- Before `createLinkedBranch`, the agent asks for the branch name, or suggests one and waits for the answer.
- Before the agent says that GitHub cannot make a link, it lists the mutations with one introspection query. The agent reads input types with one `__schema { types … }` query, not a `__type` query for each one. The agent writes both queries to files. The answer names the mutations the agent checked.
- The agent makes no link that the person did not ask for, unless a workflow they set up calls for it.
