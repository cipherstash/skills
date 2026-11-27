# Step: correctness and edge cases

Area 2, high priority. Read this, and python-practices' `references/data-modelling.md` and `references/errors.md`, before checking what the change's functions do. python-practices has no reference for correctness as such. Those two hold the traps that most often make a function break its contract, such as a shared mutable default. This file says what to look for, what evidence shows it, and what is not a finding.

## Contents

- [Check each function against its contract](#check-each-function-against-its-contract)
- [Edge cases to try](#edge-cases-to-try)
- [Evidence](#evidence)
- [Version-sensitive rules](#version-sensitive-rules)
- [Not a finding](#not-a-finding)

## Check each function against its contract

For every function or method the change adds or alters, write down its contract. That is its docstring, its name, its annotations, and what its callers rely on. Then read the body against it, one input class at a time. Report a mismatch: an input for which the function does something other than what the contract says.

When the change rewrites a line that already worked, compare the head with the base for the same inputs. A rewrite that gives a different result for some input, such as a boundary, is a consequence of the change.

When the change alters a function's behaviour, read its callers too. A caller may rely on the old behaviour, such as an error for a bad record or a sorted result. What happens to it is a consequence of the change.

## Edge cases to try

Try each of these against every changed function where it can arise:

- **Empty and `None`**:
  - an empty `str`, `list`, `dict`, or file;
  - `None` where the annotation allows it;
  - a falsy but valid value, such as `0` or `""`, tested with `if not value:`.
- **Boundaries**: one element, exact multiples, the maximum, and negative numbers. Off-by-one ranges, such as `<` against `<=`, or `range(n)` against `range(n + 1)`.
- **Rounding**: `round` rounds halves to even. `int()` truncates toward zero. `//` floors toward negative infinity.
- **Numbers**: `float()` accepts `"nan"` and `"inf"` from text. A `bool` is also an `int`. Float sums are wrong for money.
- **Indexing and keys**: `seq[0]` or `seq[-1]` on a sequence that can be empty. `mapping[key]` where the key can be missing. `next(iterator)` with no default.
- **Mutable state**:
  - a mutable default argument, as ruff's `B006` flags;
  - a dataclass field default shared between instances;
  - a cached result that callers change, as `data-modelling.md` says;
  - a list changed while it is iterated.
- **Identity and equality**: `is` used to compare values, as ruff's `F632` flags for literals. A class with `__eq__` and no `__hash__`. A mutable object used as a dict key.
- **Text and bytes**:
  - `len()` of text used as a width or a byte count;
  - text read with the platform's default encoding, where `open` needs `encoding=`;
  - `str.strip("abc")` where `removesuffix` was meant. It strips characters, not a suffix.
- **Time**:
  - a naive `datetime` compared with an aware one: it raises `TypeError`;
  - `datetime.now()` with no time zone, as ruff's `DTZ` rules flag;
  - `time.time()` used to measure a duration, where `time.monotonic()` was meant.
- **Files**: a test of `path.exists()` before a read, since the file can change between the calls. A file opened with no `with`, as `data-modelling.md` says.
- **Iterators**: a generator or iterator read twice, so the second pass is empty.

The trigger is the input. The consequence is what the function returns or does then. An uncaught exception in a function that takes input from outside the process is at least major.

## Evidence

- Reading: quote the docstring or caller that states the contract, and the line that breaks it.
- A run: a script that needs only the standard library can run at the base and the head for the input in question. Run it only where `checks.md` allows the change's code to run, and quote both outputs.
- A failing test: to show an edge case, you may add a test in the temporary worktree, as `checks.md` describes. Quote its output, and say that the test was written for the review.
- `mypy --strict` reports some of these, such as `union-attr` for an unchecked `Optional` value, or `comparison-overlap`. ruff's `B`, `RUF`, and `DTZ` rules report others.
- Coverage from the testing step shows which branches no test runs. An edge case on an untested branch is more likely to be wrong; it is not a finding by itself.

## Version-sensitive rules

Read the module's floor from step 3 before you flag a rule or suggest a fix. `str.removeprefix` and `str.removesuffix` need Python 3.9, and `datetime.UTC` needs 3.11. Suggest no fix above the floor.

## Not a finding

- An input the contract excludes, such as `None` where the docstring rules it out, unless a caller in the change passes it.
- Behaviour the docstring does not promise and no caller relies on.
- An exception the function documents for a programmer error, such as a `ValueError` for an argument out of range.
- A rounding or ordering choice that the docstring states.
- Error-handling defects, such as a lost cause or a broad `except`. They belong to the error handling area.
