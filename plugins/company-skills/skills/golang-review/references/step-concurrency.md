# Step: concurrency safety

Area 4, medium priority. Read this, and golang-practices' `references/concurrency.md`, before reviewing the change's goroutines, channels, locks, and contexts. The practices reference holds the rules and working examples. This file says what to look for in a change, what evidence shows it, and what is not a finding.

## Contents

- [Who starts, stops, and waits](#who-starts-stops-and-waits)
- [Blocking calls with no context](#blocking-calls-with-no-context)
- [Goroutines with no way to stop](#goroutines-with-no-way-to-stop)
- [Data races](#data-races)
- [Deadlocks](#deadlocks)
- [Evidence](#evidence)
- [Version-sensitive rules](#version-sensitive-rules)
- [Not a finding](#not-a-finding)

## Who starts, stops, and waits

For each goroutine, channel, lock, and context the change adds or alters, write down who starts it, who stops or cancels it, who waits for it, who sends, who closes, and what happens on the error and early-return paths as well as on success. Most concurrency defects show up as a gap in that list.

## Blocking calls with no context

A function the change adds or alters blocks when it does network or disk I/O, waits on a channel, a lock held for long, or another goroutine, or sleeps. Report it when:

- it has no `context.Context` parameter, so its caller cannot cancel it or give it a deadline;
- it has a context but calls the blocking operation without it, such as `http.NewRequest` instead of `http.NewRequestWithContext`, `db.Query` instead of `db.QueryContext`, or `time.Sleep` in a retry loop;
- it replaces the caller's context with `context.Background()` or `context.TODO()`.

The trigger is the peer hanging or the caller giving up. The consequence is a request or goroutine that stays blocked, holding its resources, after nobody wants its result.

## Goroutines with no way to stop

Report a goroutine the change starts when no path ends it, or nothing waits for it:

- a loop with no `ctx.Done()` case or other stop signal;
- a send on a channel whose receiver may have returned already, such as a result channel the caller abandons on timeout;
- a `range` over a channel that no sender is certain to close;
- a fire-and-forget goroutine whose errors and lifetime nobody owns.

The trigger is the early-return, cancel, or timeout path. The consequence is a goroutine that never ends. When the path runs once per request, the leak grows with use, which makes it major.

## Data races

Report shared state written by more than one goroutine, or written by one and read by another, with no lock, atomic, or channel handing it over:

- counters and struct fields updated from goroutines, and slices appended to from goroutines;
- maps written concurrently, which can also crash with `fatal error: concurrent map writes`;
- a `sync.Mutex` or `sync.WaitGroup` copied by value, and `wg.Add` called inside the goroutine it counts;
- a loop variable captured by a goroutine, only in a module below Go 1.22.

The consequence is lost updates, torn values, or a crash, varying from run to run.

## Deadlocks

Report a wait that can never end:

- two locks taken in different orders on different paths;
- a lock held while sending on a channel, or while calling code that can take the same lock;
- an unbuffered send whose only receiver is the sending goroutine, or is waiting for that goroutine;
- `wg.Wait()` before closing a channel that the waited-for goroutines are reading;
- a channel closed by a receiver or closed twice, which panics.

## Evidence

- `go test -race`: a race report is direct evidence. Quote the write and the earlier access with their file and line, and the line in the change that reaches them. A race-enabled pass covers only the paths the tests ran, so for changed code that no test reaches, report the race from reading and say no test exercises it. To show it, you may add a test in the temporary worktree, as `checks.md` describes.
- `go vet`: quote `copylocks`, `lostcancel`, and, below Go 1.22, `loopclosure` reports.
- A deadlock shows as `fatal error: all goroutines are asleep - deadlock!`, or as a test timeout whose goroutine dump shows the blocked calls.
- Leaks and missing contexts are usually shown by reading. Name the path that never ends and the line it blocks on. Cite a leak checker's output only if the repository already uses one, such as `goleak`.

## Version-sensitive rules

Use the `go` line in the module's `go.mod`, not the version of the installed toolchain.

- From Go 1.22, each loop iteration has its own copy of the loop variable, so a goroutine capturing it is correct. Below 1.22 it is a race, or reads the wrong value.
- Suggest only APIs the module's version has. For example, `context.WithCancelCause` needs Go 1.20, `context.AfterFunc` and `sync.OnceFunc` need Go 1.21, and `sync.WaitGroup.Go` needs Go 1.25.

## Not a finding

- A goroutine capturing a loop variable in a module at Go 1.22 or later.
- A function with no context that does only short CPU work and cannot block.
- A goroutine that is meant to outlive a request, such as a server's background worker, when it has a documented owner that stops it and waits for it.
- Unbuffered channels, or a mutex where a channel would also work, when the code is correct. That is a design preference.
