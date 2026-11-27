# Step: typing

Area 4, high priority. Read this, and python-practices' `references/typing.md`, before reviewing the change's types. The practices reference holds the rules and working examples. This file says what to look for in a change, what evidence shows it, and what is not a finding.

## Contents

- [Any where a typed value is promised](#any-where-a-typed-value-is-promised)
- [A cast that hides a real case](#a-cast-that-hides-a-real-case)
- [A type: ignore without an error code](#a-type-ignore-without-an-error-code)
- [Other typing defects](#other-typing-defects)
- [Evidence](#evidence)
- [Version-sensitive rules](#version-sensitive-rules)
- [Not a finding](#not-a-finding)

## Any where a typed value is promised

Look for a changed function whose annotation promises a type, such as `-> list[Order]` or a parameter typed `Mapping[str, int]`, but whose value is `Any`:

- a return of `json.loads(...)`, `pickle.loads(...)`, `yaml.safe_load(...)`, `response.json()`, or another call typed as returning `Any`, with no check of its shape;
- a value read from a `dict[str, Any]`, `**kwargs: Any`, or an untyped third-party call, passed on as the promised type;
- an annotation of `Any` itself, or a bare `list` or `dict`, where the type is known.

`Any` turns off mypy for every use of the value, so callers type-check against a promise nothing keeps. The trigger is input of another shape, such as a JSON object where a list was expected. The consequence is an `AttributeError`, `KeyError`, or `TypeError` far from the cause, or a wrong value that passes through. Cite the practices rule: do not use `Any` where a type is known, take `object` for a value of unknown type, and narrow it. This is `major` when the value comes from outside the process, and `minor` otherwise.

## A cast that hides a real case

Look for a changed `typing.cast(T, value)`, and an `assert isinstance(...)` used only to silence mypy, where `value` can really be something else at run time:

- `cast(str, mapping.get(key))`, where the key can be missing, so the value can be `None`;
- `cast(list[str], data)` on decoded input;
- `cast(Order, row)` on a union, where another member of the union reaches this line.

A cast does nothing at run time. It tells mypy to stop checking, so the case it hides fails later, as with `Any`. Follow the value back to where it can take the other case, and name that path.

A `cast` with no comment saying why it is true breaks the practices rule, even when it is true. That alone is `minor`. A cast the review shows to be false on a reachable path is `major`.

## A type: ignore without an error code

Look for a changed `# type: ignore` with no error code in brackets, and `# type: ignore[...]` with no comment saying why. A bare `# type: ignore` silences every error on its line, including ones the change adds later. Cite the practices rule: every `# type: ignore` names its error code and says why. ruff's `PGH003` reports a bare one. This is `minor`. Also report a `# type: ignore[...]` or a module-wide `# mypy: ignore-errors` that hides an error the review shows to be a real defect, under the defect's own severity.

## Other typing defects

The practices reference also covers these. Report them when the change introduces them:

- A function in source or tests without full annotations. It fails `mypy --strict`.
- A type check function that returns `bool` where `TypeIs` was meant, so callers narrow nothing.
- A `match` over an `Enum`, a `Literal`, or a union with no `assert_never` case, where a new member can arrive.
- Generics written with `TypeVar`, `Generic`, or `TypeAlias` where the floor allows PEP 695 syntax.

## Evidence

`mypy --strict` gives evidence for most of these, when it can run, as `checks.md` runs it.

`Returning Any from function declared to return ...` (`no-any-return`) shows a promised type kept by `Any`. `Unused "type: ignore" comment` (`unused-ignore`) shows an ignore that hides nothing. Quote the error and its line. mypy cannot see a false `cast`: read the code that reaches it.

Without the change's dependencies, mypy reports `import-not-found` or `import-untyped`, and treats those packages as `Any`. That is a limit, not a finding, and the report says which packages were missing.

## Version-sensitive rules

Read the module's floor from step 3 before you flag a rule or suggest a fix. PEP 695 generics and `type` aliases need 3.12. `typing.TypeIs` and type parameter defaults need 3.13; below that, `TypeIs` comes from `typing_extensions`. Below 3.14, a forward reference, or an import used only in annotations, is quoted. Leaving out the quotes needs 3.14.

Never flag a rule above the floor. For example, at a 3.12 floor, a quoted annotation that names a `TYPE_CHECKING` import is correct, so it is not a finding.

## Not a finding

- `Any` at a boundary that narrows it on the next lines, or `object` narrowed before use.
- A `cast` with a comment that gives a true reason.
- A `# type: ignore[code]` with a comment that gives a true reason, such as an untyped third-party call.
- A choice between equally correct annotations, such as `Sequence` or `list` for a local variable.
- Types in code the change neither adds nor makes reachable.
