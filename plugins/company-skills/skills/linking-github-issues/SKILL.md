---
name: linking-github-issues
description: Makes and checks the links GitHub stores between issues, pull requests, and branches (relates to, blocked by, sub-issues and their order, a pull request that closes an issue, duplicates, and a branch linked to an issue) with GitHub's GraphQL mutations through gh, and reads each link back. Use when linking an issue to a pull request, a branch, or another issue; when adding a sub-issue or a relates-to, blocked-by, or duplicate link; when a pull request targets a branch that is not the repository's default branch, where a Closes line does not link it; and before telling anyone that GitHub cannot link something. Not for writing an issue (filing-github-issues), opening a pull request (authoring-pull-requests), linking pull requests into a GitHub stack (stacking-pull-requests), or Linear and other issue trackers.
---

# linking-github-issues

Make the links that GitHub stores between issues, pull requests, and branches, and check each one after you make it. Every stored link has an issue at one end. Most of them appear in the issue's **Relationships** or **Development** section.

Agents often tell people that GitHub cannot make a link that it can make. Before you say that GitHub cannot link two things, check the schema, as [Before you say GitHub cannot make a link](#before-you-say-github-cannot-make-a-link) describes.

## Inputs

- **The link**: which kind of link, between which items. When the person does not name the kind, ask which one they want, and wait for the answer. Do not choose one for them.
- **The items**: each as `owner/repo#N`, a URL, or a number in the current repository. A bare number belongs to the current repository. When no current repository can be found, ask. Never take a repository from this skill's worked example.
- **Permission**: make a link only when the person asked for it, or when a workflow they set up calls for it. A link changes a record that other people read.

Needs the `gh` CLI, authenticated for the target repository. If `gh` is not installed or not authenticated, stop and tell the person.

## A mention is not a link

Writing `#NN` in an issue, a pull request, or a comment is only a mention. GitHub shows it as a cross-reference in the other item's timeline. Nothing else reads it. A mention does not make an issue a sub-issue, mark it blocked, or relate it to another issue.

When the person asks for a link, make the stored link with its mutation. Do not write a mention in its place.

## `Closes #N` links a pull request only on the default branch

A closing keyword, such as `Closes #N`, in a pull request's description links the pull request to the issue. It does so only when the pull request targets the repository's default branch.

For a pull request against any other base branch:

1. Find the default branch: `gh repo view <owner>/<repo> --json defaultBranchRef --jq .defaultBranchRef.name`.
2. Find the pull request's base: `gh pr view <number> --repo <owner>/<repo> --json baseRefName --jq .baseRefName`.
3. If they differ, link the pull request with `addCloseIssueReferences`, as [How to run a mutation](#how-to-run-a-mutation) shows.
4. Read the link back from `closingIssuesReferences` on the pull request, or from `closedByPullRequestsReferences` on the issue.

Leave any `Closes #N` line in the description as it is. Readers still use it to find the issue.

## The links

These come from GitHub's GraphQL schema, read on 11 October 2026 and checked again on 27 November 2026. `!` marks a required input. Every id is a GraphQL node id, not an issue or pull request number.

| Link | Add | Remove | Read it back on `Issue` |
|---|---|---|---|
| Relates to | `addRelatesTo(issueId!, relatedIssueId!)` | `removeRelatesTo(issueId!, relatedIssueId!)` | `relatesTo` |
| Blocked by | `addBlockedBy(issueId!, blockingIssueId!)` | `removeBlockedBy(issueId!, blockingIssueId!)` | `blockedBy`, `blocking` |
| Sub-issue | `addSubIssue(issueId!, subIssueId or subIssueUrl, replaceParent)` | `removeSubIssue(issueId!, subIssueId!)` | `subIssues`, `subIssuesSummary`, `parent` |
| Order of sub-issues | `reprioritizeSubIssue(issueId!, subIssueId!, afterId or beforeId)` | none | `subIssues` |
| Pull request that closes it | `addCloseIssueReferences(issueId!, pullRequestIds!)` | `removeCloseIssueReferences(issueId!, pullRequestIds!)` | `closedByPullRequestsReferences` |
| Duplicate | `closeIssue(issueId!, stateReason: DUPLICATE, duplicateIssueId)` | `unmarkIssueAsDuplicate(duplicateId!, canonicalId!)` | `duplicateOf` |
| Branch | `createLinkedBranch(issueId!, oid!, name, repositoryId)` | `deleteLinkedBranch(linkedBranchId!)` | `linkedBranches` |

### Which of these have been run

- **Run and checked:** `addRelatesTo` and `addCloseIssueReferences`. Sub-issues have also been added with the REST endpoint `POST /repos/{owner}/{repo}/issues/{number}/sub_issues`. The endpoint's `sub_issue_id` is the sub-issue's numeric REST `id`, not its number. Get that id with `gh api repos/<owner>/<repo>/issues/<number> --jq .id`.
- **Not yet run:** every other mutation in the table. Only the schema describes them. When you use one, read the link back, and tell the person that this skill had not seen it run before.

### What each link means

- **Relates to.** One call links both issues: each one's `relatesTo` then lists the other. "Relates to" links two issues only, never a pull request. GitHub refuses a pull request id with "Could not resolve to Issue node with the global id of …".
- **One pull request depends on another.** No mutation links one pull request to another. When asked to link two pull requests, say that "relates to" links two issues only. Then offer to write the dependency in a comment on the pull request that waits. For pull requests that each need the code in the one below, use the stacking-pull-requests skill.
- **Blocked by.** `issueId` is the issue that waits. `blockingIssueId` is the issue it waits for.
- **Sub-issue.** An issue has one parent at most. To move an issue that already has a parent, pass `replaceParent: true`. `reprioritizeSubIssue` puts a sub-issue straight after `afterId`, or straight before `beforeId`.
- **A pull request that closes the issue.** `removeCloseIssueReferences` removes only a link made by the mutation or in the sidebar. A link made by a `Closes #N` line stays until somebody edits the pull request's description. Whether the link closes the issue when the pull request merges depends on the repository's auto-close setting and on the base branch. Do not tell anyone that it will, unless you have checked both.
- **Duplicate.** No mutation marks an issue as a duplicate and leaves it open. Closing the issue with `stateReason: DUPLICATE` and `duplicateIssueId` makes the link. So this link closes the issue. Never make it unless the person asked for that issue to be closed.
- **Branch.** `createLinkedBranch` creates a new branch on GitHub at once, from the commit `oid`, linked to the issue. The name cannot change once a pull request is open from the branch. So before you call it, ask the person for the name, or suggest one and wait for their answer. `deleteLinkedBranch` takes the link's own id, from `linkedBranches`. Nobody has tested whether it also deletes the branch, so tell the person that before you call it.
- **Tracked in.** `Issue` has a `trackedInIssues` field, but no mutation sets it. Tell the person that this link cannot be made through the API, and offer a sub-issue instead.

## How to run a mutation

1. **Write the GraphQL to a file** in a temporary directory, not in the person's repository. Do this for every query, including the introspection queries below. Pass it with `gh api graphql -F query=@<file>`, and each variable as `-f name=value`. Typed on the command line, the braces can make some agent sandboxes refuse the command.
2. **Look up the node ids.** One query can fetch several, with an alias for each:

   ```graphql
   query {
     repository(owner: "OWNER", name: "REPO") {
       i: issue(number: 101) { id }
       p: pullRequest(number: 102) { id }
     }
   }
   ```

   For items in different repositories, add one `repository` block for each, with its own alias.
3. **Run the mutation.** For example, to link a pull request that closes an issue:

   ```graphql
   mutation($i: ID!, $p: ID!) {
     addCloseIssueReferences(input: { issueId: $i, pullRequestIds: [$p] }) {
       issue { number closedByPullRequestsReferences(first: 10, includeClosedPrs: true) { nodes { number } } }
     }
   }
   ```

   ```sh
   gh api graphql -F query=@link.graphql -f i=<issue node id> -f p=<pull request node id>
   ```
4. **Read the link back** from the field in the table's last column, in a separate query. A mutation's answer says that GitHub accepted the request. The answer does not show what the issue shows now.

If GitHub answers with an error, report the error text as it is. Do not retry with a mention or a comment in place of the link.

### Worked example

This example records one past fix. Never use its repository or numbers for a new link.

On 27 November 2026, two pull requests in `cipherstash/stack` targeted `next`, but the default branch was `main`. Each had `Closes #N` in its description. Neither was linked. `addCloseIssueReferences` linked `cipherstash/stack#1912` to `#1849`, and `#1913` to `#1848`. `closedByPullRequestsReferences` on each issue then listed its pull request.

## Before you say GitHub cannot make a link

1. List every mutation with GitHub's own description of it:

   ```graphql
   query { __schema { mutationType { fields { name description } } } }
   ```

   ```sh
   gh api graphql -F query=@mutations.graphql --jq '.data.__schema.mutationType.fields[].name'
   ```

2. Read the input types of the mutations that might fit. GitHub refuses a query that uses one introspection field more than twice, with "Introspection fields may only be used 2 times". So do not ask `__type(name: …)` once for each input type. Ask for every type in one query, and pick out the types you need with `--jq`:

   ```graphql
   query { __schema { types { name inputFields { name type { kind } } } } }
   ```

   ```sh
   gh api graphql -F query=@types.graphql --jq '.data.__schema.types[] | select(.name == "AddBlockedByInput")'
   ```

3. Say that GitHub cannot make the link only when no mutation fits. Name the mutations you checked. Then offer what GitHub can do instead, such as a comment on the item that waits.

## Boundaries

- Make a link only when the person asked for it, or when a workflow they set up calls for it.
- Never close an issue to mark it a duplicate unless the person asked for it to be closed.
- Never remove a link that you did not make unless the person asked.
- Never write a `#NN` mention in place of a link the person asked for.

## Report

For each link, give the two items, the mutation you ran, and what the read-back showed. Say which mutations had not been run before this skill used them. Name any link you could not make, with GitHub's error text.
