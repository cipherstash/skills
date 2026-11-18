---
name: review-assessment
description: Decides which company review skills a change needs — review-golang, review-rust with rust-security, review-typescript, review-python, review-infracode, review-test-gaps — and returns a review plan with one reason per skill, from a script that maps changed file paths the same way every run. Use when asked which reviews a pull request, branch, or diff needs, and as the routing step of review-code. Does not review the code, report findings, or post anything; performing the review is review-code.
argument-hint: "<PR URL, branch, base ref, or working diff>"
---

# review-assessment

Produce a review plan: the review skills a change needs and why. Do not review the code.

## 1. List the changed files

Use the comparison the caller already fixed (review-code records it in its step 1). Otherwise resolve the PR, branch, commit range, or working changes, and ask for the target or base if it cannot be inferred. List every changed path relative to the repository root, including deleted, renamed, and relevant untracked files — for example `git diff --name-only <base>...<head>`, or `gh pr diff <PR> --name-only` for a PR.

If the file list cannot be read, or is truncated, stop and report that. Never return an empty plan for a change you could not read.

## 2. Run the assessment script

Pipe the paths, one per line, to `scripts/assess.py` in this skill's directory (resolve it from the installed skill, not the working directory). It needs only Python 3.

```sh
git diff --name-only <base>...<head> | python3 <skill dir>/scripts/assess.py
```

It prints JSON:

```json
{
  "plan": [
    {"skill": "review-rust", "reason": "Rust code or Cargo files changed"},
    {"skill": "rust-security", "reason": "Every Rust change gets a secret-handling and cryptography pass"}
  ],
  "unmatched": ["README.md"]
}
```

`plan` rows come from file paths only: Go, Rust, TypeScript/JavaScript, and Python code and manifests select their language specialist; every Rust change also selects `rust-security`; GitHub workflows, Dockerfiles, and Terraform select `review-infracode`; code changed with no test file changed selects `review-test-gaps`. `unmatched` lists paths no language or infrastructure rule matched. Exit 2 means no paths were given: stop as in step 1.

## 3. Add what the paths cannot show

Read the diff for each `unmatched` path and for content a path does not reveal: a YAML workflow that runs Python, a generator whose output another language consumes, a shell script in CI, a lockfile whose consumers changed, or tests that changed without the code they protect. Add a row for each skill those signals need, with its reason, and mark it `judgement`. Read review-code's routing table for which skill covers which signal.

You may add rows. You may not drop or downgrade a row the script printed, even when it looks unnecessary — say why in the plan instead. If the user explicitly narrows the review, keep the row and mark it excluded by the user so the exclusion is reported. Documentation-only and other unmatched paths with no executable effect need no specialist: list them as needing an accuracy pass by the coordinator. For a language with no specialist, say that no specialist exists.

## 4. Return the plan

Return one line per row: the skill, its reason, and its origin (`script` or `judgement`). Then list unmatched paths and how each is covered. Keep the script's JSON alongside when the caller needs it verbatim. Hand the plan to review-code, or to the user when they asked only which reviews to run.
