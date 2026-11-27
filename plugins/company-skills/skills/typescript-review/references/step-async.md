# Step: async and concurrency

Area 5, medium priority. Read this, and typescript-practices' `references/async.md`, before reviewing the change's promises, `await`s, timers, listeners, and `AbortSignal`s. The practices reference holds the rules and working examples. This file says what to look for in a change, what evidence shows it, and what is not a finding.

## Contents

- [Who starts, waits, and cancels](#who-starts-waits-and-cancels)
- [Un-awaited promises](#un-awaited-promises)
- [Waits with no way to cancel](#waits-with-no-way-to-cancel)
- [Leaks that grow with use](#leaks-that-grow-with-use)
- [Shared state across `await`](#shared-state-across-await)
- [Unbounded work](#unbounded-work)
- [Evidence](#evidence)
- [Not a finding](#not-a-finding)

## Who starts, waits, and cancels

For each promise, timer, listener, stream, and `AbortSignal` the change adds or alters, write down who starts it, who waits for it, who handles its rejection, who cancels or removes it, and what happens on the error and early-return paths as well as on success. Most async defects show up as a gap in that list.

## Un-awaited promises

Report a promise that nothing awaits, returns, or handles:

- a call to an `async` function, or one that returns a promise, as a bare statement;
- an `async` callback passed where the caller ignores the result: `forEach`, `map` whose result is not awaited with `Promise.all`, an event listener, `setTimeout`, or a constructor;
- `Promise.all` or `Promise.allSettled` whose own result is not awaited;
- `return` instead of `return await` inside a `try`, so a rejection skips the `catch` (the error handling area reports this one);
- background work started with `void` but with no `.catch()` and no comment saying why nothing waits.

Follow what happens next. The function resolves before the work is done, so its caller acts on a result that is not ready yet: it reports success, closes a connection, or exits. A rejection nobody handles is an unhandled rejection, which ends the Node process by default. The trigger is the call rejecting, with an example cause, or the caller reading state the work had not finished. A dropped error or a result reported before the work is done is `major`. It is `critical` when the review shows the unhandled rejection in a common path, such as every request.

## Waits with no way to cancel

A function the change adds or alters waits when it calls the network, a timer, a file, or a child process, or polls. Report it when:

- it takes no `AbortSignal`, so its caller cannot cancel it or give it a deadline;
- it takes a signal but does not pass it to a call that accepts one, such as `fetch`, `setTimeout` from `node:timers/promises`, or a stream;
- it times out with `Promise.race` against a timer, which leaves the losing call running;
- it catches the abort and carries on, instead of cleaning up and rethrowing.

The trigger is the peer hanging or the caller giving up. The consequence is work that keeps running, holding its sockets, files, or memory, after nobody wants its result.

## Leaks that grow with use

Report a timer, interval, listener, or pending promise the change adds that nothing ends: an `addEventListener` on a long-lived signal or emitter with no `removeEventListener` or `{ once: true }`; a `setInterval` with no `clearInterval`; a promise kept in a `Map` that nothing deletes. When the path runs once per request or per call, the leak grows with use, which makes it `major`.

## Shared state across `await`

Code between two `await`s runs without interruption; any `await` lets other code run. Report a read, then an `await`, then a write based on the read, of state that other calls change: a counter, a cache, or a check-then-set such as "if not cached, fetch and store". The trigger is two calls at once; the consequence is a lost update, a duplicate fetch, or a stale value. Name the two calls and the interleaving.

## Unbounded work

Report a map from a list of any length to promises that all start at once, where each opens a connection, a file, or a native call: name the list's source and its size. With no bound shown, it is `minor`. It is `major` when the list comes from outside the process, so its size is someone else's choice.

## Evidence

- Reading: quote the line that starts the work and the line that should have awaited or cancelled it.
- oxlint's type-aware `no-floating-promises` and `no-misused-promises` rules report un-awaited promises and `async` callbacks in the wrong place, but they need the change's dependencies, so they are usually a limit: quote CI's oxlint result for the head commit instead, when there is one.
- A test written for the review, using `vi.useFakeTimers()` or a promise that never settles, can show a race or a leak. It runs the change's code, so it runs only where `checks.md` allows tests to run.

## Not a finding

- Background work marked with `void`, with a `.catch()` that logs and a comment that gives a reason that holds.
- A promise returned to a caller that awaits it.
- A missing `AbortSignal` on a function that does no I/O and waits on no timer.
- Two calls that share no state, run at once.
