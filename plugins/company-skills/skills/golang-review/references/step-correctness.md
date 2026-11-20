# Step: correctness and edge cases

Area 2, high priority. Read this, and golang-practices' `references/error-handling.md` and `references/interfaces.md`, before checking what the change's functions do. golang-practices has no reference for correctness as such: those two hold the language traps that most often make a function do something other than what it says, such as a typed nil error or a one-value type assertion. This file says what to look for, what evidence shows it, and what is not a finding.

## Contents

- [Check each function against its contract](#check-each-function-against-its-contract)
- [Edge cases to try](#edge-cases-to-try)
- [Evidence](#evidence)
- [Not a finding](#not-a-finding)

## Check each function against its contract

For every function or method the change adds or alters, write down its contract: the doc comment, the name, the types, and what its callers in the repository rely on. Then read the body against it, one input class at a time. Report a mismatch: an input for which the function does something other than what the contract says.

When the change alters a function's behaviour, read its callers too. A caller that relied on the old behaviour, such as an error for a bad record or a sorted result, is a consequence of the change.

## Edge cases to try

Try each of these against every changed function where it can arise:

- **Empty and nil**: an empty or `nil` slice, map, or string; a `nil` pointer, interface, function, or channel; a zero-value struct. A method on a `nil` pointer receiver.
- **Division and indexing**: division by a value that can be zero, which panics for integers; `s[0]`, `s[len(s)-1]`, or `s[i:j]` on a slice that can be shorter; a map read that assumes the key exists.
- **Boundaries**: one element, the maximum, negative numbers, and off-by-one ranges (`<` against `<=`). Integer overflow when sizes or money are multiplied.
- **Types**: a one-value type assertion `x.(T)` that panics when `x` holds another type; a nil pointer of a concrete type returned as an interface, which is not `nil`; a struct compared with `==` when it holds a slice or map, which does not compile, or a pointer, which compares identity.
- **Text**: `len(s)` used as a character count on non-ASCII text, and byte indexing that splits a rune.
- **Time**: wall-clock time used to measure durations, time zones, and comparisons with `==` on `time.Time`, which compares the location too. Use `Equal`.
- **Copies and aliasing**: a slice returned that shares its array with the caller's input, and `append` to it changing the caller's data; a value receiver that modifies a copy, so the change is lost.
- **Defaults**: a zero value that the code treats as valid, such as a zero timeout meaning "wait forever".

The trigger is the input; the consequence is what the function returns or does then. A panic in a function that takes input from outside the process is at least major.

## Evidence

- Reading: quote the doc comment or caller that states the contract, and the line that breaks it.
- A failing test in the temporary worktree: to show an edge case, you may add a test there that calls the function with that input, as `checks.md` describes, and quote its output. Say that the test was written for the review.
- `go vet` reports some of these: unreachable code, impossible comparisons, and `printf` mismatches. `staticcheck`, when installed, reports more, such as a nil dereference after a nil check.
- Coverage from the testing step shows which branches no test runs. An edge case on an untested branch is more likely to be wrong; it is not a finding by itself.

## Not a finding

- An input the contract excludes, such as a `nil` argument that the doc comment says must not be nil, unless a caller in the change passes it.
- Behaviour the doc comment does not promise and no caller relies on.
- A panic on a programmer error that the function documents, such as a `Must` helper.
- A rounding or ordering choice that the doc comment states.
