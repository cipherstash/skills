# Step: documentation

Area 10, low priority. Read this, and python-practices' `references/project-structure.md` (its section on docstrings), before reviewing the change's documentation. The rule is a docstring on every public module, class, and function, with no required style. This file says what to report.

## Contents

- [Missing docstrings](#missing-docstrings)
- [Stale documentation](#stale-documentation)
- [Evidence](#evidence)
- [Version-sensitive rules](#version-sensitive-rules)
- [Not a finding](#not-a-finding)

## Missing docstrings

Report each public name the change adds with no docstring. A public name is a module, class, function, or method with no leading underscore, in a module that is not private. Group them into one finding that lists every location.

A docstring that only repeats the name or the annotations, such as `"""The user ID."""` on `user_id: int`, says nothing a caller must know. Report it only when the function raises an error or has an effect the caller must know about, and the docstring leaves it out.

Tests, and private helpers whose name and types explain them, need no docstring.

## Stale documentation

Report text the change makes wrong:

- a docstring on a changed function, class, or module that no longer matches the code. Check what it does, its arguments, its return value, its errors, and whether threads or tasks may share it;
- a README, a `docs/` page, a usage message, or `--help` text that still describes the old behaviour, arguments, settings, or API. Search the repository's Markdown and reStructuredText files and its docstrings for the changed names, options, and settings;
- a doctest whose output the change makes wrong. The test run shows that as a failure, when doctests run.

A stale docstring is a finding when a reader would be misled. Quote the stale text and the line that contradicts it. When the stale text describes a defect another step reports, mention it there instead.

## Evidence

- Reading the diff, and the docstring of each changed name at the base and the head, read with `git show`. A docstring unchanged at a function whose arguments changed is a place to look.
- A search of the repository's documentation for the changed names.
- The suite has no ruff `D` rules, so no tool reports a missing docstring. Do not run ruff with `D` selected.

## Version-sensitive rules

Read the module's floor from step 3 before you flag a rule or suggest a fix. No documentation rule here depends on the version.

## Not a finding

- A docstring's wording, length, or style, such as Google, NumPy, or reStructuredText, when it is accurate.
- A missing docstring on a private name, or in a test.
- Documentation of code the change does not touch, unless the change makes it wrong.

Documentation findings are `minor`, unless stale text would lead a user to do harm. An example is a README that still shows a removed safety flag.
