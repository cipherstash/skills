# Release memory after a cancel followed by a trap

If a Go program uses `WithCloseOnContextDone(true)` with a custom `experimental.MemoryAllocator`, read this file. Read it too when you review a change to that allocator. It expands section 9 of `SKILL.md`.

## Contents

- The bug in one paragraph
- How to reproduce it
- Why the interpreter is not affected
- The host-side defence
- Cautions
- Status of the fix

## The bug in one paragraph

On the compiler engine in wazero v1.12.0, a context that ends during a host call marks the module closed.

The watcher leaves the release of memory and file descriptors to the next check for a closed module. If the guest traps, calls `proc_exit` or overflows its stack before that check, the call ends by a panic path that never performs the release. Calling `module.Close` or `runtime.Close` afterwards does nothing, because the module is already marked closed. `LinearMemory.Free` is never called. Source: wazero/wazero#2558, and a reproduction on v1.12.0.

## How to reproduce it

Build a guest that imports a `cancel` host function and exports two functions. The first calls `cancel` and then `proc_exit`. The second calls `cancel` and then runs `unreachable`.

The host function cancels the call's context. It then sleeps for 50 ms, so that the context watcher can mark the module closed. Give the call a context that contains a `MemoryAllocator`. Its `LinearMemory.Free` records that it ran.

On v1.12.0, with the compiler engine, both calls end with the module reported closed, `Close` returns nil, and `Free` was never called. If the host function does not cancel, `Free` is called in both cases. The full program is in the issue.

A real guest that returns normally does not show the bug, because a normal return reaches the closed-module check. Only a trap, `proc_exit`, or a stack overflow between the cancel and the next check shows it. Test with a synthetic trapping guest on your own allocator, as well as with your real guest.

A later call on the closed module that returns normally also performs the release. Tests against the CipherStash Go SDK showed this. The guest aborted after a cancel. Without a free of the staged buffer, some runs left the memory unreleased. With that free inside the allocator's in-flight bracket, no run did.

So an `IsClosed` guard on that free can bring the leak back. Section 10 of `SKILL.md` gives the rule.

## Why the interpreter is not affected

The interpreter engine runs the closed-module check in its deferred function before it recovers from the panic. The compiler engine runs it only on the path where the call did not panic.

In v1.12.0, compiled code checks for a closed module at three points.

The first is every loop header (`internal/engine/wazevo/frontend/lower.go`). The second is a normal return from a call. The third is the start of a nested call under a cancelled context (`internal/engine/wazevo/call_engine.go`). A trap or stack overflow in the gap skips the release. Reading the v1.12.0 source and running the reproduction above confirmed this.

## The host-side defence

After `runtime.Close` returns, call the allocator's own free on every memory it created. Make that free run only once, so a second call, from wazero or from the host, does nothing.

```go
type trackedMemory struct {
    inner experimental.LinearMemory
    once  sync.Once
}

func (m *trackedMemory) Reallocate(size uint64) []byte { return m.inner.Reallocate(size) }

// Free releases the memory once, however many times it is called.
func (m *trackedMemory) Free() { m.once.Do(m.inner.Free) }

type trackingAllocator struct {
    inner experimental.MemoryAllocator
    mu    sync.Mutex
    mems  []*trackedMemory
}

func (a *trackingAllocator) Allocate(capacity, maxBytes uint64) experimental.LinearMemory {
    m := &trackedMemory{inner: a.inner.Allocate(capacity, maxBytes)}
    a.mu.Lock()
    a.mems = append(a.mems, m)
    a.mu.Unlock()
    return m
}

// ReleaseAll frees every memory that wazero did not free. Call it only after
// runtime.Close has returned and no call is running.
func (a *trackingAllocator) ReleaseAll() {
    a.mu.Lock()
    defer a.mu.Unlock()
    for _, m := range a.mems {
        m.Free()
    }
    a.mems = nil
}
```

Use one allocator for each runtime or each run, so that `ReleaseAll` frees only memory that belongs to that owner. Remove a memory from the list when its instance closes normally if the list could grow without bound.

## Cautions

- Free only when the guest has stopped. Freeing mapped memory under a running guest crashes the process. One project made its `Close` cancel the runs in progress and wait for them. If the wait times out, `Close` returns an error and leaves the runtime open.
- The `once` is needed. When wazero does release the memory, a second free could unmap an address range that the operating system has since given to something else.
- Files that the guest opened are also not closed in this case. A host-side defence cannot close them. Only a wazero fix does.
- The defence is harmless after wazero is fixed, so it does not need removing at once. Re-run the reproduction after each wazero upgrade, and remove the defence when the fix is in the version you use.

## Status of the fix

wazero/wazero#2558 describes the bug.

The pull request wazero/wazero#2561 fixes it. It makes the compiler engine run the closed-module check however the call ends.

It also makes `Close` release deferred resources once, using a compare-and-swap. The pull request was open when this was written. The fork samyfodil/wazy has the same fix in pull request #81. That pull request is merged in the fork. Check the state of #2561 before you advise a version.
