# Behavior cases

## Should activate

- "Rewrite this README in plain language."
- "This incident report is too hard for the support team to follow. Can you make it clearer?" with the report attached.
- "Review this design doc for jargon and tell me what to change."
- "Write up the findings from the load test for the leadership team" — the skill applies the Part 3 guidelines for findings and measurements.
- "Make this plainer" with no text attached and no file named — the skill asks which text to change before it drafts anything.

## Should not activate

- "Refactor this function to remove the duplicated loop" — code, not prose.
- "Generate API reference docs from these Rust doc comments" — generated reference output.
- "Fix the typo on line 12 of CHANGELOG.md" — a one-word edit, not a plain-language rewrite.

## Expected behavior

- The skill reads `references/core.md` before it drafts, and names the reader, their purpose, and their context before it writes a new document or a rewrite.
- A rewrite lists every fact in the original first, and the final check confirms each fact is present or reports which ones were cut on purpose.
- A review reports each problem with the sentence, the ISO 24495 clause or GOV.UK rule it breaks, and a suggested rewrite, and does not rewrite the whole text unless the user asks.
- The skill runs `python3 <skill dir>/scripts/check.py` on each prose file it writes, resolving the script from the installed skill directory rather than the user's project, fixes every "must fix" finding, and decides on each "consider" finding.
- When the checker exits 2 because the project's `.plain-language.json` is broken, the skill reports the named file and the reason, and does not treat the run as passing.
- When a checker finding is wrong, such as a listed word used literally, the skill rephrases the sentence anyway and tells the user which rule fired, so they can change `scripts/rules.json`.
- When Python 3 is not available, the skill still follows the steps and the reread in step 5b, and tells the user the checker did not run.
- Where the repository has its own style guide or writing rules in CLAUDE.md or AGENTS.md, the skill follows them as well, and they win where they are stricter.
- The skill never quotes the text of ISO 24495-1 or ISO 24495-3; it paraphrases and cites the clause.
- For a document many people will read, or one where a misunderstanding is costly, the skill tells the user that testing with a real reader is the only way to know the document works.
