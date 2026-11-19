# Behavior cases

`test_assess.py` covers `scripts/assess.py` through its command line: `python3 -m unittest discover -s tests` from the skill directory.

## Should activate

- "Which review skills does PR 42 need?"
- "Before reviewing this branch against main, tell me which specialists should look at it and why."
- review-code's routing step, on any review it runs.
- "What reviews does this need?" with no PR, branch, or diff given and none inferable — the skill asks for the target or base.

## Should not activate

- "Review PR 42" — that is review-code, which runs this skill as its routing step.
- "Which review threads on PR 42 are still open?" — review-audit.
- "Fix the findings from the review" — review-fix.

## Expected behavior

- The plan comes from `scripts/assess.py` run on the full changed-file list; the same files give byte-identical JSON on every run.
- A mixed Rust and Terraform change with no test file changed plans review-rust, rust-security, review-infracode, and review-test-gaps, and nothing else from the script.
- A Go change that includes its `_test.go` file plans review-golang without review-test-gaps.
- A documentation-only change plans no specialist; its files are listed as unmatched, with no specialist.
- The agent does not treat the script's plan as complete: it judges every listed skill against the diff. A Rust change whose only test file is an unrelated Go test still gets review-test-gaps, and a public Rust API change gets rust-sdk-dx, each with origin `judgement`.
- The agent adds a row the script missed — for example review-python for a workflow that runs an inline Python script — with its reason and origin `judgement`.
- The agent never drops or downgrades a script row because it judges the row unnecessary. When the user narrows the focus ("skip the Rust security pass"), the row stays in the plan marked as excluded by the user, so review-code reports it as an excluded area.
- An unreadable or truncated file list, or the script exiting 2, stops with an explicit error; no empty plan is returned.
- The skill reviews nothing: it reports no findings and posts nothing.
