# Embedding wazero

Go code that runs WebAssembly modules with the wazero runtime: host functions, shared modules, context cancellation, guest memory, and custom memory allocators. It covers how the host uses wazero, not the guest's own source.

The advice targets wazero v1.12.0 and Go 1.22, the `go` line in [`examples/go.mod`](../examples/go.mod). This reference has no Go examples, because they would need wazero, and the examples module uses only the standard library. The Go module path is still `github.com/tetratelabs/wazero`. The repository is now `github.com/wazero/wazero`. On another wazero version, check each rule against that version's documentation first.

Each rule comes from a bug that another project hit. Some of those bugs are fixed. Others are still open. [Sources](#sources) gives the evidence for each one.

## Contents

- [Terms](#terms)
- [What to look for](#what-to-look-for)
- [1. A panic in a host function breaks the instance](#1-a-panic-in-a-host-function-breaks-the-instance)
- [2. Concurrent calls on one module, or a close during a call](#2-concurrent-calls-on-one-module-or-a-close-during-a-call)
- [3. Context cancellation closes the module](#3-context-cancellation-closes-the-module)
- [4. A slice from `Memory().Read` used after the guest frees or grows memory](#4-a-slice-from-memoryread-used-after-the-guest-frees-or-grows-memory)
- [5. A guest free export called with the wrong number of arguments](#5-a-guest-free-export-called-with-the-wrong-number-of-arguments)
- [6. Deterministic defaults in production](#6-deterministic-defaults-in-production)
- [7. Memory growth that is never returned](#7-memory-growth-that-is-never-returned)
- [8. A `CompiledModule` reused across runtimes](#8-a-compiledmodule-reused-across-runtimes)
- [9. Memory is not released after a cancel followed by a trap](#9-memory-is-not-released-after-a-cancel-followed-by-a-trap)
- [10. A call into a closed module after its memory is freed](#10-a-call-into-a-closed-module-after-its-memory-is-freed)
- [11. Projects that may not need wazero](#11-projects-that-may-not-need-wazero)
- [Example: a guest SDK that applies these rules](#example-a-guest-sdk-that-applies-these-rules)
- [Detail: release after a cancel followed by a trap](#detail-release-after-a-cancel-followed-by-a-trap)
- [Detail: the cleanup order around a closed module](#detail-the-cleanup-order-around-a-closed-module)
- [Sources](#sources)

## Terms

- The **host** is your Go program. The **guest** is the WebAssembly module that wazero runs.
- A **host function** is a Go function that the guest can call.
- **Linear memory** is the one block of memory that a guest module reads and writes. The block grows in pages. It never shrinks.
- A **trap** is a guest failure. Examples are `unreachable`, an out-of-bounds access, and a stack overflow. wazero reports a trap as an error from the call that caused it.
- `proc_exit` is the call that a guest makes, through the WebAssembly System Interface (WASI), to stop itself. wazero ends the call with an exit code.

## What to look for

Search the code for each pattern in the first column. Then read the matching section.

| Look for | Section |
| --- | ---: |
| `panic(`, or an unchecked error, inside a function registered with `NewHostModuleBuilder` | 1 |
| A module, `api.Function`, or runtime in a package variable, a struct shared by goroutines, or a `sync.Pool`. Any `Close` that can run during a call | 2 |
| `WithCloseOnContextDone(true)`, or a context with a deadline passed to `Call`, followed by reuse of the same module | 3 |
| A `Memory().Read` result that outlives the next `Call`, a `free`, or a return from the function | 4 |
| `Call(ctx, ptr)` on an export that takes more than one parameter, or a `Call` whose error is dropped | 5 |
| `wazero.NewModuleConfig()` without `WithRandSource` and the clock options, in code that does real work | 6 |
| Long-lived modules whose memory grows, a pool that drops modules without `Close`, many runtimes in one process | 7 |
| A `CompiledModule` that is instantiated on a different runtime from the one that compiled it | 8 |
| `WithCloseOnContextDone(true)` together with a custom `experimental.MemoryAllocator` that holds memory outside the Go heap | 9 |
| A guest export called, including a deferred `free`, after the call that staged its buffers has ended, with an allocator that unmaps memory | 10 |

## 1. A panic in a host function breaks the instance

**What goes wrong.** wazero recovers a panic in a host function. It returns the panic as an error from `Call`, and the error text contains `(recovered by wazero)`. The guest's frames are abandoned in the middle of execution. The guest normally restores its shadow stack pointer before it returns. After a panic, the pointer stays lowered.

Each such call uses up a fixed amount of the guest's stack.

After enough calls, every later call on the instance fails with `wasm error: out of bounds memory access`. That includes calls that would otherwise succeed. In one report, a DNS outage of 24 seconds caused about 20 panics. The client stayed broken until the process restarted. Go heap size, process memory, and goroutine counts stay flat, so monitoring does not show the fault.

The reports do not show whether other traps leave guest state the same way. That is an inference. Treat an instance that has trapped as suspect.

**How to spot it.**
- A host function that calls `panic`, or lets a library panic through, for an expected failure. Network errors, timeouts, and bad input are expected failures.
- A cache or singleton that hands out the same instance again after an error.

**Fix.**
- Return failures to the guest through the guest's own error path. A status code or an error buffer works. Keep `panic` for states that cannot be recovered. The Extism go-sdk report proposes this for `http_request`. The maintainers asked for the error to go through Extism's own error mechanism, with part of the message if possible.
- After a trap or an `out of bounds memory access`, discard the instance and create a new one. Do not keep calling it.
- Discard the instance itself. Evicting a cached wrapper is not enough when a library keeps one shared instance for the whole process, as the 1Password SDK does. The new wrapper then runs on the same broken instance.
- To know that an instance still works, make a probe call into the guest after errors. A liveness check that does not call the guest stays green.

References: 1Password/onepassword-sdk-go#288, extism/go-sdk#102, external-secrets/external-secrets#6941, kradalby/ts1p#2.

## 2. Concurrent calls on one module, or a close during a call

**What goes wrong.** wazero documents `api.Function.Call` as not safe for concurrent use. A call must not start before the previous call on the same function returns.

A module has one linear memory. Most guests also have one heap allocator. A sequence of `malloc`, `Memory().Write`, `Call`, `Memory().Read`, and `free` must therefore run as one unit. Concurrent use corrupts the guest heap and the call engine's stack. Many of the failures cannot be recovered:
- `fatal error: runtime: split stack overflow`
- `unsafe.Slice: len out of range`
- `unexpected return pc`
- a nil pointer dereference
- a `SIGSEGV` that kills the process with no Go traceback

A `recover` does not catch these.

A close during a call causes the same kind of failure.

In one project, a recovery path closed an instance in a background goroutine while other goroutines were still calling it. A caller received a nil `api.Function` and cached it. The next call crashed the process.

**How to spot it.**
- A module, function handle, or runtime in a package variable, or shared by several goroutines or sessions.
- A mutex that covers one decoder or session but not the module that they share.
- A `Close`, replace, reload, or recovery path that does not take the same lock as the calls.
- Package-level initialisation without a lock or `sync.Once`.
- Guest state that lasts across calls, such as a parser with reassembly buffers.

**Fix.** Pick one of these.
- **One instance for each goroutine or session.** Compile once, then instantiate many times. This is wazero's documented pattern. Each instance has its own linear memory and globals. Each owner closes its own instance.
- **A lock around every entry into the shared instance.** Hold the lock for the whole `malloc`, write, call, read, copy, and `free` sequence. Take the same lock in `Close` and in every entry point, including small ones such as `Name` or `Version`. Keep a lock order that cannot deadlock.

Whichever you pick, also do these:
- Set a closed flag under the lock. Late callers then get a clear error, such as `ErrModuleClosed`, and not a freed instance.
- Check the result of `ExportedFunction`. Never cache a nil handle.
- Initialise once. Hold one mutex through load and publish, and use the same mutex for release.
- Test with `go test -race` and many goroutines. [checks.md](checks.md) gives the command CI runs. Add a test that closes during a call.

References: spotify/confidence-resolver#511 and #512, 1Password/onepassword-sdk-go#18 and #285, hoophq/hoop#1574, daltoniam/switchboard#181, llehouerou/go-faad2#1, meokit/opus#1, flipt-io/flipt-client-sdks#787 (closed without merging).

## 3. Context cancellation closes the module

**What goes wrong.** With `WithCloseOnContextDone(true)`, a context that ends during a call closes the whole module.

The call returns a `sys.ExitError`, and the module stays closed. Later calls fail with `module closed with context deadline exceeded`. The message names the previous call's context, not the current one. One request timeout then disables the library for every later request.

Code that keeps using the module after the failed call can also panic. In one project, a deferred `free` ran on a module field that the cancel path had set to nil.

Closing a runtime while `CompileModule` runs is also unsafe in wazero v1.12.0. The compile can write to a type table that `Close` has already cleared. It panics with `assignment to entry in nil map`, and the panic ends the whole process.

**How to spot it.**
- `WithCloseOnContextDone(true)` with one long-lived module that serves many requests.
- A request-scoped context passed to `Call` on a shared module.
- Deferred cleanup that calls into the module after a failed call.
- A runtime that a cancel path can close while a compile or instantiate is still running.

**Fix.** Choose one of these.
- Leave close-on-context-done off. Check the context only before the call starts. A running call is then not interrupted. Say so in the documentation. One project chose this.
- Turn it on, and treat a cancel as the end of that instance. Detect the closed module with `sys.ExitError` or `Module.IsClosed`. Build a new instance for the next call. Use a pool, so one cancel does not stop other callers. Apply section 2 as well.
- Give guest calls their own deadline, separate from the caller's context. Do this when a client that disconnects must not cancel work that is already running.

Also do these:
- Guard cleanup that runs after a failed call has ended. Check for a closed or nil module, and return early. Section 10 gives one exception: a free inside a custom allocator's in-flight bracket must still run.
- Keep the runtime open until compile and instantiate return. Let a `Close` mark the run as closed. Let the code that is compiling release the runtime afterwards, once.

References: goccy/go-graphviz#118, forkcloser/go-graphviz#139, chennqqi/zxing#4, netsec-ethz/debuglet#175 and #219.

## 4. A slice from `Memory().Read` used after the guest frees or grows memory

**What goes wrong.** `Memory().Read` returns a view of the guest's memory. It does not return a copy. The wazero documentation says so.

The guest overwrites the view when it reuses the block, for example when a deferred `free` writes allocator data into it. The view is also cut off from the memory when the guest grows its memory.

A host that returns the view, stores it, or reads it after the next call sees corrupted data. The corruption is quiet. In one image decoder, the first few pixels were wrong, and only for some colour encodings.

**How to spot it.** Look for a `Read` result that is returned, assigned to a field, sent on a channel, or used after a `free` or another `Call`. Look for a `defer free(...)` that runs before the result is copied.

**Fix.**
- Copy the bytes out before anything else runs on the instance: `out := make([]byte, n); copy(out, view)`.
- Make the copy inside the same locked section as the call (section 2).
- Never hand a view to a caller.
- Never return guest-allocated memory directly. One project did, and the guest freed the memory on return. Later calls then read corrupted data.

References: flipt-io/flipt-client-sdks#761, gen2brain/jpegxl#5 (open).

## 5. A guest free export called with the wrong number of arguments

**What goes wrong.** wazero checks the number of parameters at run time. `Call(ctx, ptr)` on an export that takes `(ptr, size)` returns an error and does not run the function. Code that drops that error frees nothing. An example is `defer m.free.Call(ctx, ptr)` with an `errcheck` suppression.

Guest memory then fills up. The guest eventually fails with `malloc error: module closed with exit_code(4)`, `out of bounds memory access`, or a nil pointer dereference. Trivy had this bug in two call sites.

**How to spot it.** Look for a `Call` whose error is ignored, or hidden by a linter suppression. Compare the number of arguments in each `Call` with the guest's exported signature. `ExportedFunctionDefinitions()` and `ParamTypes()` give the signature.

**Fix.**
- Pass every parameter that the signature lists.
- Check the error from every `Call`, including deferred frees. Log it or return it.
- Put the free in one helper, so one place knows the signature. The helper can tolerate a guest that has no `free` export, if that is allowed.
- Add a test that allocates, frees, and asserts that the free returns no error.

References: aquasecurity/trivy#10256 (closed) and #11316 (open).

## 6. Deterministic defaults in production

**What goes wrong.** `wazero.NewModuleConfig()` is built for reproducible sandboxing. The random source behind `random_get` is deterministic, so every instance produces the same bytes. The wall clock and the monotonic clock are fakes, and sleep returns at once. You must switch on the real ones.

The effects that projects saw:
- identical CSRF tokens and identical custom IDs
- identical UUIDs and primary key collisions across pooled instances
- predictable password salts and session tokens
- a JavaScript obfuscator whose randomness was defeated

**How to spot it.** Look for `NewModuleConfig()` in code that does real work, with no `WithRandSource`. Look for pools of instances that all start from the same default. Look for guests that use `crypto/rand`, hash-map seeds, UUIDs, tokens, timestamps, or timeouts.

**Fix.** For production, call these methods on the config that `wazero.NewModuleConfig()` returns:
- `WithRandSource(rand.Reader)`, with `rand` imported from `crypto/rand`
- `WithSysWalltime()` and `WithSysNanotime()`, for the real clocks
- `WithSysNanosleep()`, for a real sleep

Keep the deterministic defaults only in tests that need reproducible output. Say so in a comment. If instances share one random source, the source must be safe for concurrent reads. `crypto/rand.Reader` is safe.

References: extism/go-sdk#87, traefik/traefik#14107, crowdsecurity/crowdsec#4496, e6qu/sharecrop#184.

## 7. Memory growth that is never returned

**What goes wrong.** Guest linear memory can grow. It cannot shrink, because the WebAssembly specification does not allow it. When large and small allocations mix, the guest's allocator fragments its heap. New large blocks then force new pages, and the old pages stay.

wazero's default allocator keeps linear memory in a Go `[]byte`. A `memory.grow` past the buffer's capacity may reallocate the buffer and copy it. The Go heap can reach about twice the guest's size.

A pool that drops modules without closing them leaks a whole runtime each time. One project used a `sync.Pool`. Go clears that pool on every garbage collection, and each cleared entry kept its memory and its compiled code.

**How to spot it.**
- A `sync.Pool` or cache that stores modules or runtimes, with no `Close` on eviction.
- A new `wazero.NewRuntime` for each request, module, or pool entry, with no shared compilation cache.
- A long-lived instance that swaps large state in place.
- No limit on guest memory.

**Fix.**
- Close every instance and runtime that you stop using. For a pool, use a bounded pool that closes what it does not keep. Or run `Close` from a cleanup that fires when an entry is collected.
- Share one runtime and one `CompiledModule`, or one `CompilationCache`, between instances. Instantiate for each use.
- Replace a long-lived instance with a fresh one when its state is replaced. In one project, load time stayed at 170 to 200 ms per load. The live Go heap fell from 243 MB to 117 MB.
- Flush guest-side buffers before a large update. Skip updates when the state has not changed.
- Set a limit with `WithMemoryLimitPages`.
- If the Go heap is the problem, supply an `experimental.MemoryAllocator`. It reserves address space once and commits pages as the guest grows, so growth does not copy. Two projects did this with `mmap`.

A custom allocator brings duties. The memory must be freed (section 9). The guest must have stopped before the memory is unmapped. A failed reservation needs a fallback to a heap buffer, because wazero cannot handle a nil `LinearMemory`.

References: spotify/confidence-resolver#455 and #665, EasyTier/EasyTier#2782, grafana/gcx#1484, warpstreamlabs/bento#1087 (open).

## 8. A `CompiledModule` reused across runtimes

**What goes wrong.** `CompileModule` stores numeric function type IDs in the `CompiledModule`. The IDs come from the compiling runtime's store. A store assigns IDs in the order it first sees each type, so the same signature gets different IDs in two runtimes.

In wazero v1.12.0, instantiating a module on a different runtime from the one that compiled it can fail. The error looks like this: `import func[...]: signature mismatch: i32i64i32i32_i64 != i32i64i32i32_i64`. The two printed signatures are identical. The error prints the structural signature, but the comparison uses the IDs.

Versions v1.9.0 to v1.11.0 did not fail. An upgrade can therefore break working code. The bug is a regression in wazero. The wazero main branch fixed it after v1.12.0, in commit 236c245 ("store should recompute type IDs at instantiation time"). No release contained the fix when this reference was written.

**How to spot it.** Look for a package-level `CompiledModule` that is compiled on a throwaway runtime and instantiated on others. Look for a pinned or newly bumped wazero v1.12.0.

**Fix.**
- Compile on the runtime that instantiates.
- Share compile work through `wazero.NewCompilationCache()` on the runtime config. This avoids the compile cost and keeps the type IDs correct.
- Move to a wazero release that has the fix once one is published.

References: fastschema/qjs#50 (open). Its author closed the proposed change because wazero fixed the bug upstream.

## 9. Memory is not released after a cancel followed by a trap

**What goes wrong.** This bug needs `WithCloseOnContextDone(true)` on the compiler engine in v1.12.0. A cancel marks the module closed. wazero leaves the release of its resources to the next closed-module check. The guest may trap, call `proc_exit`, or overflow its stack before that check. Then the release never happens.

`LinearMemory.Free` is not called, and file descriptors stay open. A later `module.Close` or `runtime.Close` finds the module already closed. The call returns nil and does nothing. The interpreter engine is not affected.

The default allocator hides this, because the garbage collector reclaims the memory. A custom allocator that depends on `Free` leaks the memory for good. An allocator that uses `mmap` is one example.

In v1.12.0, compiled code checks for a closed module at three points:
- at loop headers
- when a call returns normally
- at the start of a nested call under a cancelled context

A trap or stack overflow between the cancel and the next check skips the release. In tests, a guest that returned normally released its memory in every case. A synthetic guest that trapped right after the cancel leaked every time.

**How to spot it.** Look for a custom `MemoryAllocator`, or any resource that wazero releases through the module. Check whether the same code uses `WithCloseOnContextDone(true)` on the default compiler engine.

**Fix.**
- Upgrade to a wazero release that contains the fix once one exists. The bug is wazero/wazero#2558. The proposed fix is wazero/wazero#2561. It was still open when this reference was written. The fork samyfodil/wazy has the fix in #81.
- Until then, add a host-side defence. Record every memory that your allocator hands out. After `runtime.Close` returns, call each memory's own free directly. Make that free run only once, because wazero may also call it.

[Detail: release after a cancel followed by a trap](#detail-release-after-a-cancel-followed-by-a-trap) has the reproduction, the defence, and the cautions.

References: wazero/wazero#2558, wazero/wazero#2561 (open), samyfodil/wazy#81.

## 10. A call into a closed module after its memory is freed

**What goes wrong.** wazero v1.12.0 does not check for a closed module when a call starts. `callEngine.Call` goes straight to `callWithStack` (`internal/engine/wazevo/call_engine.go`, lines 181 to 191).

`callWithStack` checks the call's context only when `WithCloseOnContextDone(true)` is set (lines 254 to 264). With that option off, it makes no check at all. So a call runs the guest on a closed module when the option is off. It also does so when the call's context cannot end, such as `context.Background()`.

This is harmless while the memory is a Go slice. It is fatal when a custom allocator has unmapped the memory. The guest then runs on an address range that no longer exists. Go reports `unexpected fault address` and `fatal error: fault [signal SIGSEGV]`, or `fatal error: runtime: split stack overflow`. `recover` cannot catch either, and the process stops.

The usual trigger is a cleanup call. A cancel closes the module during a call. The allocator unmaps the memory when the call ends. A later `free` or `se_dealloc` call on a staged buffer then runs guest code on unmapped memory.

**How to spot it.**
- A custom allocator that unmaps in `Free`, and code that calls a guest export after the call that staged its buffers has ended.
- A deferred `free` of a host-staged buffer that runs after the allocator's in-flight bracket has ended. The bracket is a pair of calls around each guest call. It lets the allocator hold back a `Free` until the call ends. For example, the stack SDK names the pair `Enter` and `Exit`.
- A new call into an export that does not first check `Module.IsClosed`. A free inside the bracket is the exception, as **Fix** explains.
- A `Close` or cancel path that frees memory without waiting for calls in progress.

**Fix.**
- Free host-staged buffers inside the allocator's in-flight bracket, before `Exit`. With `defer`, register the free after the `Exit` defer, because Go runs defers in reverse order.
- Check `IsClosed` before `Enter`, and before any call after `Exit`.
- Run a free inside the bracket even when `IsClosed` is true. After a cancel, the module reports closed while its memory is still mapped, so the free is safe. Its normal return is also one of the section 9 checks that releases the memory. Without the free, memory can stay unreleased after a cancel followed by a trap.
- Never call an export on a module whose memory is freed. Guest buffers are gone with that memory, so skip the free.
- Hold back a `Free` that arrives during a call, and run it at the matching `Exit`. For example, the stack SDK's allocator does this.
- Pin the order. Add a comment on the defers, and a regression test that runs the wrong order in a child process and expects a fault.

[Detail: the cleanup order around a closed module](#detail-the-cleanup-order-around-a-closed-module) has the sequence, the tests, and their results.

References: wazero v1.12.0 `internal/engine/wazevo/call_engine.go` lines 181 to 191 and 254 to 264.

## 11. Projects that may not need wazero

wazero suits code that loads modules at run time. A project may run only one known module, and may be limited by interpreter speed or start-up time. That project may do better by translating the module to Go at build time. ncruces/go-sqlite3 moved from wazero to wasm2go for performance and start-up time. The author expects users to see no difference.

This is background for a design discussion. It is not a review finding.

References: ncruces/go-sqlite3#362 and its discussion, ncruces/go-sqlite3/discussions/361.

## Example: a guest SDK that applies these rules

The CipherStash Go SDK runs Rust guests on wazero v1.12.0. It lives in `languages/golang` in `github.com/cipherstash/stack`. It uses `WithCloseOnContextDone(true)` and a custom `MemoryAllocator` that maps, locks, and wipes memory. Its host functions call back into the guest through an `se_alloc` export.

Those choices raise the questions in sections 2, 3, 4, 7, 9, and 10. Use it as a worked case. Read its code before you copy anything.

In that SDK, `guest.Call` runs `mem.Enter()`, then `defer mem.Exit()`, then registers the deferred free of staged buffers. Go runs defers in reverse order, so the buffers are freed before `Exit`. The details below record tests of that order.

## Detail: release after a cancel followed by a trap

This expands section 9. Read it if a Go program uses `WithCloseOnContextDone(true)` with a custom `experimental.MemoryAllocator`. Read it too when you change that allocator.

### The bug in one paragraph

On the compiler engine in wazero v1.12.0, a context that ends during a host call marks the module closed.

The watcher leaves the release of memory and file descriptors to the next check for a closed module. If the guest traps, calls `proc_exit` or overflows its stack before that check, the call ends by a panic path that never performs the release. Calling `module.Close` or `runtime.Close` afterwards does nothing, because the module is already marked closed. `LinearMemory.Free` is never called. Source: wazero/wazero#2558, and a reproduction on v1.12.0.

### How to reproduce it

Build a guest that imports a `cancel` host function and exports two functions. The first calls `cancel` and then `proc_exit`. The second calls `cancel` and then runs `unreachable`.

The host function cancels the call's context. It then sleeps for 50 ms, so that the context watcher can mark the module closed. Give the call a context that contains a `MemoryAllocator`. Its `LinearMemory.Free` records that it ran.

On v1.12.0, with the compiler engine, both calls end with the module reported closed, `Close` returns nil, and `Free` was never called. If the host function does not cancel, `Free` is called in both cases. The full program is in the issue.

A real guest that returns normally does not show the bug, because a normal return reaches the closed-module check. Only a trap, `proc_exit`, or a stack overflow between the cancel and the next check shows it. Test with a synthetic trapping guest on your own allocator, as well as with your real guest.

A later call on the closed module that returns normally also performs the release. Tests against the CipherStash Go SDK showed this. The guest aborted after a cancel. Without a free of the staged buffer, some runs left the memory unreleased. With that free inside the allocator's in-flight bracket, no run did.

So an `IsClosed` guard on that free can bring the leak back. Section 10 gives the rule.

### Why the interpreter is not affected

The interpreter engine runs the closed-module check in its deferred function before it recovers from the panic. The compiler engine runs it only on the path where the call did not panic.

In v1.12.0, compiled code checks for a closed module at three points.

The first is every loop header (`internal/engine/wazevo/frontend/lower.go`). The second is a normal return from a call. The third is the start of a nested call under a cancelled context (`internal/engine/wazevo/call_engine.go`). A trap or stack overflow in the gap skips the release. Reading the v1.12.0 source and running the reproduction above confirmed this.

### The host-side defence

After `runtime.Close` returns, call the allocator's own free on every memory it created. Make that free run only once, so a second call, from wazero or from the host, does nothing.

Build the defence as a wrapper around your allocator:
- Wrap each `experimental.LinearMemory` that the inner allocator returns. The wrapper passes `Reallocate` through. Its `Free` calls the inner `Free` through a `sync.Once`.
- Keep a list of the wrapped memories, guarded by a mutex. The wrapping allocator's `Allocate` adds each new memory to the list.
- Add a release method that calls `Free` on every memory in the list, then clears the list. Call it only after `runtime.Close` has returned. No call may be running then.

Use one allocator for each runtime or each run, so that the release frees only memory that belongs to that owner. Remove a memory from the list when its instance closes normally if the list could grow without bound.

### Cautions

- Free only when the guest has stopped. Freeing mapped memory under a running guest crashes the process. One project made its `Close` cancel the runs in progress and wait for them. If the wait times out, `Close` returns an error and leaves the runtime open.
- The `sync.Once` is needed. When wazero does release the memory, a second free could unmap an address range that the operating system has since given to something else.
- Files that the guest opened are also not closed in this case. A host-side defence cannot close them. Only a wazero fix does.
- The defence is harmless after wazero is fixed, so it does not need removing at once. Re-run the reproduction after each wazero upgrade, and remove the defence when the fix is in the version you use.

### Status of the fix

wazero/wazero#2558 describes the bug.

The pull request wazero/wazero#2561 fixes it. It makes the compiler engine run the closed-module check however the call ends.

It also makes `Close` release deferred resources once, using a compare-and-swap. The pull request was open when this was written. The fork samyfodil/wazy has the same fix in pull request #81. That pull request is merged in the fork. Check the state of #2561 before you advise a version.

## Detail: the cleanup order around a closed module

This expands section 10. Read it if an allocator unmaps guest memory, and your code calls guest exports around that point.

### The sequence

1. A call into the guest starts. The allocator marks it in flight with `Enter`.
2. The call's context ends during a host function. wazero's watcher closes the module and defers the release of its resources.
3. The guest re-enters or returns. wazero asks the allocator to `Free` the memory. The allocator holds the request back, because a call is in flight.
4. The call ends. `Exit` performs the held `Free`. The memory is now wiped and unmapped.
5. Code that runs after step 4 calls an export, such as `se_dealloc` to free a staged buffer.

wazero v1.12.0 does not check for a closed module when a call starts. The guest runs on unmapped memory and the process dies with a fault.

Step 5 is the whole bug. Freeing the staged buffer before step 4 is safe, because the memory is still mapped.

### What the test does

The test is in the CipherStash Go SDK's module, in a copy outside the repository. It has two cases. Each runs in its own process, because the test binary re-runs itself with `-test.run` and an environment variable. A leaked memory lock then cannot break the next case.

Both cases stage a buffer by hand and call `se_cipher_init`. A harness cancels the call's context at the first host function and waits for the module to close. The cases differ in one line.

- **Wrong order.** The test calls `Exit`, then frees the staged buffer.
- **Correct order.** The test frees the staged buffer, then calls `Exit`.

The wrong-order parent asserts that the child exited with a fatal runtime error. The correct-order parent asserts that the child passed. In the child, it asserts that the module is closed, that the call returned an error, and that `Allocator.IsFreed()` is true after `Client.Close`.

### Results

Each case ran at least 8 times in its own process on Linux with wazero v1.12.0 and Go 1.26.10.

- **Wrong order.** The process died every time. Most deaths were `unexpected fault address` and `fatal error: fault [signal SIGSEGV]`. A few were `fatal error: runtime: split stack overflow`. Both come from the same fault in compiled code, and `recover` does not catch either. A test that checks for one message only will fail now and then. Check for a fatal runtime error.
- **Correct order.** No crash in any run. The module was closed. The memory was freed after `Client.Close`.

### Cautions for your own test

- Run each case in its own process. A crash ends the process. Leaked locked memory stays locked until the process exits, and `RLIMIT_MEMLOCK` can be as low as 8 MiB.
- Skip the wrong-order case when the allocator falls back to a heap buffer. The memory then stays valid and nothing faults.
- Free with `context.Background()` in the wrong-order case. A context that is already done makes wazero close the module and return an error before it runs guest code. That would hide the bug.
- Wait for the module to close after the cancel. The watcher closes it on another goroutine.

## Sources

Read this when you need the evidence behind a rule, or want to cite a report in a review. Every item was opened and read. Each fix was read where one exists. States are as found on 2026-11-19. They can change, so check a state again before you quote it.

References are `owner/repo#number`. Pull requests and issues share one number space per repository.

### 1. Panic in a host function

- 1Password/onepassword-sdk-go#288 (issue, open). A long-lived client, a DNS outage, then every call fails with `out of bounds memory access` after about 20 panics in `http_request`. A comment reproduces it with a proxy that refuses connections and traces it to the Extism host function.
- extism/go-sdk#102 (issue, open). The `http_request` host function calls `panic(err)` when the request fails. The guest's `__stack_pointer` drops by about 51,632 bytes per failed call from 1,048,576 and wraps below zero on the 20th, after which every call fails. A patch that returns status 0 and an empty response instead of panicking removed the problem in testing. The reporter notes it discards the real error. The maintainer asked for the error to go through Extism's error mechanism.
- external-secrets/external-secrets#6941 (issue, open). The operator caches the SDK client and never evicts it, so every secret stays unready until restart. A comment explains that evicting the client would not help while the SDK keeps one core for the process.
- kradalby/ts1p#2 (issue, open). Same failure under sustained uptime. The project's workaround has five parts. It retries once. It exits the process on confirmed corruption. It can recycle the instance on a schedule. It gives calls their own deadline. It counts each fault on a debug page.

### 2. Concurrent calls and close during a call

- spotify/confidence-resolver#511 (issue, closed). Exit 139 with no traceback, about 16 a week across about 150 pods. Core dumps show a nil `api.Function`. Recovery closed an instance while other resolves were mid-call.
- spotify/confidence-resolver#512 (PR, merged). `Close` now takes the call mutex. The accessor for exported functions panics with a clear message instead of returning nil and never caches nil.
- 1Password/onepassword-sdk-go#18 (PR, merged). One mutex around `plugin.Call` on the shared core.
- 1Password/onepassword-sdk-go#285 (PR, merged). One lifecycle mutex covers cold initialisation, publish, and release. Concurrent first callers then do not build duplicate runtimes.
- hoophq/hoop#1574 (PR, merged). One shared parser instance across sessions corrupted state and crashed the gateway. Fix: compile once behind `sync.Once`, instantiate one isolated instance per session, validate required exports at construction, return real errors. Tests run eight concurrent sessions under `-race`.
- daltoniam/switchboard#181 (PR, merged). A per-module call mutex around every entry point and an atomic closed flag that gives `ErrModuleClosed`. Crashes had been a nil dereference in a memory read helper and a runtime traceback fatal error.
- flipt-io/flipt-client-sdks#787 (PR, closed without merging). Quotes the wazero rule that `Call` is not goroutine-safe. It says function handles should not be stored on a shared client. Cite it for the rule, not as a fix.
- llehouerou/go-faad2#1 (PR, open). A per-decoder mutex did not cover the shared runtime. Adds a process-wide mutex held for each whole `malloc`, write, call, read, `free` sequence. Lock order is fixed.
- meokit/opus#1 (PR, open). A mutex on the shared context around encode, decode, control calls, and reset. Reproduces `fatal error: runtime: split stack overflow` with two encoders.

### 3. Cancellation closes the module

- goccy/go-graphviz#118 (issue, open). After one render is cancelled by a timeout, every later call fails with `module closed with context deadline exceeded`.
- forkcloser/go-graphviz#139 (issue, closed). In the fork the runtime has no close-on-done and one module per process. The fix is PR #200 in that fork. It honours a context until the call starts. It does not interrupt a running layout. The documentation says so.
- chennqqi/zxing#4 (issue, open). On cancel the code sets `r.module = nil`, and deferred free helpers then dereference it. Proposed: return early from the free helpers when the module is nil or closed. The runtime rebuilds on the next call.
- netsec-ethz/debuglet#175 (issue, closed) and #219 (PR, merged, included in integration PR #228). Closing a runtime during `CompileModule` on v1.12.0 panics with `assignment to entry in nil map` and ends the process. Fix: while a compile runs, `Close` only marks the run closed. The initialiser releases the runtime and compiled module exactly once afterwards and returns `net.ErrClosed`. Compile time itself is not interrupted.

### 4. Slices from Memory().Read

- flipt-io/flipt-client-sdks#761 (PR, merged). Returned memory that the guest had allocated and then freed on return. This corrupted later calls. Also fixes a double close of a channel and a blocking read that ignored shutdown.
- gen2brain/jpegxl#5 (PR, open). `img.Pix` aliased a `Memory().Read` view, and deferred frees overwrote the first pixels. Fix: `copy` into the buffer that `image.NewNRGBA64` allocates. The new test fails on main and passes with the fix.

### 5. Free called with the wrong arguments

- aquasecurity/trivy#10256 (PR, closed). `free` takes `(ptr, size)`. Two call sites passed only `ptr`, wazero returned an arity error, and `errcheck` was suppressed. Memory filled until the module failed with `module closed with exit_code(4)`. Fix: pass both arguments. Adds a signature test.
- aquasecurity/trivy#11316 (PR, open). The same bug fixed by a helper that passes pointer and size and tolerates a missing export.

### 6. Deterministic defaults

- extism/go-sdk#87 (issue, closed). A Rust guest's `rand::random` returned the same value on every call under the Go host. The fix is `WithRandSource(rand.Reader)`.
- traefik/traefik#14107 (PR, merged). Concurrent requests produced identical custom IDs. Fix: use operating-system randomness.
- crowdsecurity/crowdsec#4496 (PR, merged). Gives wazero a proper random source because the default defeated the randomness of a JavaScript obfuscator.
- e6qu/sharecrop#184 (PR, merged). Twelve pooled instances shared one predictable `crypto/rand` stream. Effects: UUID collisions, primary key violations, predictable salts, and predictable tokens. Fix: `crypto/rand.Reader` in both module configs that run a guest, and a test that needs distinct tokens from the pool.

### 7. Memory growth

- spotify/confidence-resolver#455 (issue, closed). Interleaved large state updates and small log allocations fragment the guest's allocator, so pages are added and never returned. Two related fixes are merged. #469 flushes logs before a state update. #502 skips the update when the state is unchanged.
- spotify/confidence-resolver#665 (issue, closed). In-place updates hold about 2.3 times the memory a state needs (85 MB, 140 MB, 195 MB for a 29 MB state). The issue proposes a fresh instance for each later state, with the old one closed. #666 makes that change and is open. #678 is merged. Its change keeps one copy of the state while the next loads.
- spotify/confidence-resolver#665 and #666 also measure the fresh-instance change. Load time stayed at 170 to 200 ms per load. After the old instance was closed and collected, the live Go heap fell from 243 MB to 117 MB.
- EasyTier/EasyTier#2782 (PR, merged). Guest memory moved off the Go heap with a reserved mapping that commits pages as the guest grows, plus one shared in-memory compilation cache. At 400 connections, resident memory fell from about 526 MB to about 265 MB.
- grafana/gcx#1484 (PR, merged). The same off-heap approach on Linux. Peak fell from 3,902 MiB to 2,122 MiB. The PR also makes `Close` cancel the runs and wait for them. It gives each run its own allocator and frees it itself, because of the bug in section 9. It falls back to a heap buffer when the reservation is refused.
- warpstreamlabs/bento#1087 (issue, open). A `sync.Pool` of module runners is cleared on every garbage collection. Nothing closes the runners. The patch is a bounded pool that closes what it drops. A maintainer comment lists other causes: one runtime per module, and no close on collection.

### 8. CompiledModule across runtimes

- fastschema/qjs#50 (PR, open). With wazero v1.12.0, `qjs.New()` failed with identical signatures printed as mismatched. Cause: the `CompiledModule` stores type IDs from the compiling runtime, and v1.12.0 compares them. The author closed the change after wazero fixed it on the main branch in commit 236c2458ed22 (`store should recompute type IDs at instantiation time`, wazero PR 2511). That commit is six commits after v1.12.0. v1.12.0 was the latest release when this was written.

### 9. Release after cancel then trap

- wazero/wazero#2558 (issue, open). Full reproduction and cause. See [Detail: release after a cancel followed by a trap](#detail-release-after-a-cancel-followed-by-a-trap).
- wazero/wazero#2561 (PR, open). Makes the closed-module release run however a call ends and lets `Close` release deferred resources once, through a compare-and-swap. Adds tests on both engines for exit, trap, and stack overflow.
- samyfodil/wazy#81 (PR, merged in the fork). The same fix in the fork, with tests for trap, `proc_exit`, host panic, stack overflow, and normal return.

### 10. Call into a closed module after its memory is freed

- wazero v1.12.0, `internal/engine/wazevo/call_engine.go`. `callEngine.Call` (lines 181 to 191) goes straight to `callWithStack`. `callWithStack` (lines 254 to 264) checks whether the context is done. It makes that check only when `WithCloseOnContextDone(true)` is set.
- A test in the CipherStash Go SDK's module, run on 2026-11-19, confirmed the crash and the safe order. See [Detail: the cleanup order around a closed module](#detail-the-cleanup-order-around-a-closed-module).

### 11. Moving away from wazero

- ncruces/go-sqlite3#362 (PR, merged). Switches from wazero to wasm2go. The discussion (ncruces/go-sqlite3/discussions/361) gives two reasons: slow interpreter performance, and slow start-up on compiler targets. It also says wazero stays right for loading modules at run time.

### Notes on wazero documentation

These statements come from the v1.12.0 documentation in `api/wasm.go` and `config.go`:

- `Function.Call` is not goroutine-safe. Do not call it again before the previous call returns. Sequential calls are allowed.
- `Memory.Read` returns a view, not a copy. The view is disconnected when the memory capacity changes.
- With `WithCloseOnContextDone`, a call that ends because of the context closes the module and returns `sys.ExitError`.
- `WithRandSource` defaults to a deterministic source. The wall clock, the monotonic clock, and sleep default to fakes.
- `LinearMemory.Reallocate` may return nil on failure. `Free` releases the backing buffer.

### Reference check

All references given for this reference were confirmed to exist. None was dropped.
