# Step: error handling

Area 1, high priority. Read this, and golang-practices' `references/error-handling.md`, before reviewing the change's error handling. The practices reference holds the rules and working examples. This file says what to look for in a change, what evidence shows it, and what is not a finding.

## Contents

- [Ignored errors](#ignored-errors)
- [Errors returned without context](#errors-returned-without-context)
- [Other error-handling defects](#other-error-handling-defects)
- [Code that embeds wazero](#code-that-embeds-wazero)
- [Evidence](#evidence)
- [Version-sensitive rules](#version-sensitive-rules)
- [Not a finding](#not-a-finding)

## Ignored errors

Look in every changed line for a call that returns an error the code never checks:

- A call used as a statement, so all its results are dropped: `json.Unmarshal(b, &v)`, `w.Write(p)`, `tx.Rollback()`, `os.Remove(path)`.
- An error assigned to `_` with no comment saying why it cannot matter.
- An `err` assigned and then overwritten by a later call before anything reads it.
- An `err` checked in the wrong scope: `x, err := f()` inside an `if` or `for` block shadows the outer `err`, which is what the function returns.
- `defer f.Close()` on a file or writer the code wrote to. Close can be where a write failure first shows, so the error is lost.
- `rows.Err()` never checked after a `for rows.Next()` loop, and errors from goroutines that never reach whoever waits for them.

For each one, follow what the code does next when the call fails. The trigger is the call failing, with an example cause. The consequence is what the code does with bad or missing state: counts a bad record, returns success, writes a partial file. If the change removed a check or a test that the base had, say so: it is part of the cause.

## Errors returned without context

Look for `return err` or `return nil, err` in changed code where the caller cannot tell from the message what failed: which operation, or which input. It matters most where a function makes several fallible calls or reads several inputs, and where an error leaves the package. The consequence is a log line such as `unexpected EOF` with nothing to say which file or record caused it. Cite the practices rule on adding context. This is usually minor, unless a caller is shown to depend on the message.

Also look for a wrap with `%v` or `%s` where `%w` was meant. That breaks `errors.Is` and `errors.As` for callers. It is major when a caller in the repository matches the wrapped error, and minor otherwise.

## Other error-handling defects

The practices reference also covers these. Report them when the change introduces them:

- An error compared with `==` or a type assertion where it may be wrapped. `errors.Is` or `errors.As` sees through the wrapping.
- An error logged and then returned, so the same failure is reported twice.
- A nil pointer of a concrete error type returned as `error`. The caller's `err != nil` is then true even on success.
- A `panic` for a failure that can happen at run time, such as bad input or a failed I/O call.

## Code that embeds wazero

When a changed package imports `github.com/tetratelabs/wazero`, also read golang-practices' `references/wazero.md`. Its sections 1 and 5 list the error-handling cases:

- A host function that panics for an expected failure, such as a network error. After wazero recovers the panic, the guest's stack pointer stays lowered. After repeated errors, every call on the instance fails.
- An instance used again after a trap or a recovered panic.
- A guest export called with the wrong number of arguments, or a `Call` whose error is dropped, such as a deferred free. The free does not run, and guest memory fills up.

Show a wrong argument count by comparing the `Call` with the export's signature in the guest's source.

## Evidence

No standard tool finds every ignored error. Most findings in this area come from reading the change, so quote the line and the code path that shows the consequence. `go vet` helps in a few places: misused `%w` in `fmt.Errorf`, and `errors.As` given a non-pointer. Cite its output when it reports one. Run `errcheck` or `staticcheck` only if already installed.

## Version-sensitive rules

Read the module's Go version before suggesting a fix. `errors.Is`, `errors.As`, and `%w` need Go 1.13. `errors.Join`, and more than one `%w` in one `fmt.Errorf`, need Go 1.20. Below those versions, suggest a fix that compiles.

## Not a finding

- An error deliberately ignored with `_ =` and a comment whose reason holds, or a deferred `Close` on something only read.
- Calls documented never to return a non-nil error, such as `bytes.Buffer.Write`, `strings.Builder.WriteString`, and `hash.Hash.Write`.
- An error returned unwrapped from a function that makes a single call and adds nothing a caller could use, where the message already names the operation and input.
- Error string style: capitalisation, punctuation, or a "failed to" prefix. That belongs to the naming and style area, not this one.
- Error handling in code the change neither adds nor makes reachable.
