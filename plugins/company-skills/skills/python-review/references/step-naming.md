# Step: naming and style

Area 6, medium priority. Read this, and python-practices' `references/project-structure.md` (its section on naming and style), before reviewing names and formatting in the change. This file says what to report and how.

## Contents

- [What to report](#what-to-report)
- [Formatting](#formatting)
- [Severity](#severity)
- [Version-sensitive rules](#version-sensitive-rules)
- [Not a finding](#not-a-finding)

## What to report

In names the change adds or renames:

- **Case**: a function, method, variable, or module not in `snake_case`; a class or type alias not in `PascalCase`; a module constant not in `UPPER_SNAKE_CASE`.
- **Error classes**: an exception class whose name does not end in `Error`.
- **Names for the type**: a name for its type, not for what it is, such as `user_list` for `users`. A function that returns `bool` and does not read as a question, such as `valid` for `is_valid`.
- **Private names**: two leading underscores where no name mangling is needed. A name meant to be private, with no leading underscore, in a module that exports it.
- **Imports**:
  - an import below the top of the file with no reason, such as a cycle or a slow optional import;
  - an import used only in annotations outside `if TYPE_CHECKING:`, as ruff's `TC` rules flag.
- **Paths and formatting**:
  - `os.path` and `pathlib` mixed in one module;
  - `%` or `.format` where an f-string fits. A logging call is the exception: it takes `%s` arguments.

Group repeats of one problem into one finding that lists every location.

## Formatting

Run `ruff format --check --diff` over the changed `.py` and `.pyi` files that still exist at the head, as `checks.md` describes. Each line it would change is part of one formatting finding per file: quote the lines `--diff` removes. Never run `ruff format` without `--check`: the review changes no file. Also report a `# fmt: off` or `# fmt: skip` the change adds with no reason, since the rule is to leave the formatter's output as it is.

`ruff check` gives evidence for the import rules. `I` flags unsorted imports, and `TC` flags imports used only in annotations. `E402` flags an import below the top, and `PTH` flags `os.path`.

## Severity

Naming and style findings are `minor`. They break a rule, with no effect when the code runs. A rename that breaks importers belongs to the breaking changes step. That step sets its own severity.

## Version-sensitive rules

Read the module's floor from step 3 before you flag a rule or suggest a fix. ruff's `UP` rules depend on the target version. Run ruff with the floor as `--target-version`. Report no `UP` rule that the floor does not allow.

## Not a finding

- A name in code the change does not add or rename.
- A short name in a short scope, such as `i`, `k`, or `fh`.
- A name that follows the repository's own documented convention where it differs from python-practices. Say which convention you followed.
- A naming preference with no rule behind it.
- Docstring wording or a missing docstring. That belongs to the documentation area.
