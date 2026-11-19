---
name: golang-wazero
description: Applies lessons from real bugs in Go programs that embed the wazero WebAssembly runtime, to review or write that code. Covers panics in host functions, concurrent calls and close during a call, context cancellation closing the module, slices from Memory().Read, guest free calls with the wrong arguments, deterministic random and clock defaults, memory that never shrinks, CompiledModule reuse across runtimes, memory that is not released after a cancel followed by a trap, and calls into a closed module after its memory is freed. Use when reviewing or writing Go code that imports github.com/tetratelabs/wazero, such as wazero.NewRuntime, InstantiateModule, api.Function.Call, host function builders, WithCloseOnContextDone, or experimental.MemoryAllocator. Does not apply to other WebAssembly runtimes (wasmtime, Wasmer, Extism's non-Go hosts), to the guest side written in Rust or C, or to Go code that does not use wazero.
user-invocable: false
---

# Embedding wazero in Go

These rules apply to Go code that runs WebAssembly modules with wazero. Each rule comes from a bug that another project hit. Some of those bugs are fixed. Others are still open. The evidence for each bug class is in [references/sources.md](references/sources.md).

The advice targets wazero v1.12.0. The Go module path is still `github.com/tetratelabs/wazero`. The repository is now `github.com/wazero/wazero`. On another version, check each rule against that version's documentation first.

Terms used below:

- The **host** is your Go program. The **guest** is the WebAssembly module that wazero runs.
- A **host function** is a Go function that the guest can call.
- **Linear memory** is the one block of memory that a guest module reads and writes. The block grows in pages. It never shrinks.
- A **trap** is a guest failure. Examples are `unreachable`, an out-of-bounds access, and a stack overflow. wazero reports a trap as an error from the call that caused it.
- `proc_exit` is the call that a guest makes, through the WebAssembly System Interface (WASI), to stop itself. wazero ends the call with an exit code.

## How to use this skill

When you review, search the changed code for each pattern in the first column. Then read the matching section. When you write, check your code against each section before you finish.

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

A finding needs a trigger and a consequence, not only a pattern. Name the input or the timing that makes the code fail.

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
- Test with `go test -race` and many goroutines. Add a test that closes during a call.

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

**Fix.** Set these options on the module config for production:

```go
cfg := wazero.NewModuleConfig().
    WithRandSource(rand.Reader). // crypto/rand
    WithSysWalltime().
    WithSysNanotime().
    WithSysNanosleep()
```

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

Versions v1.9.0 to v1.11.0 did not fail. An upgrade can therefore break working code. The bug is a regression in wazero. The wazero main branch fixed it after v1.12.0, in commit 236c245 ("store should recompute type IDs at instantiation time"). No release contained the fix when this skill was written.

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
- Upgrade to a wazero release that contains the fix once one exists. The bug is wazero/wazero#2558. The proposed fix is wazero/wazero#2561. It was still open when this skill was written. The fork samyfodil/wazy has the fix in #81.
- Until then, add a host-side defence. Record every memory that your allocator hands out. After `runtime.Close` returns, call each memory's own free directly. Make that free run only once, because wazero may also call it.

[references/release-on-cancel.md](references/release-on-cancel.md) has the code, the reproduction, and the cautions.

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

**Example: the stack SDK.** `guest.Call` runs `mem.Enter()`, then `defer mem.Exit()`, then registers the deferred free of staged buffers. Go runs defers in reverse order, so the buffers are freed before `Exit`.

A real test confirmed both orders. A cancel closed the module during a call.

With the free after `Exit`, the child process died on every run. Most runs gave `unexpected fault address` and SIGSEGV. A few gave `split stack overflow`.

With the free before `Exit`, the child never crashed. The module was closed. `Allocator.IsFreed()` was true after `Client.Close`. [references/closed-module-order.md](references/closed-module-order.md) has the details.

A second test made the guest abort after a cancel. Without the free of the staged buffer, some runs left the memory unreleased. With the free inside the bracket, no run did. [references/release-on-cancel.md](references/release-on-cancel.md) has the details.

References: wazero v1.12.0 `internal/engine/wazevo/call_engine.go` lines 181 to 191 and 254 to 264.

## 11. When wazero is the wrong tool

wazero suits code that loads modules at run time. A project may run only one known module, and may be limited by interpreter speed or start-up time. That project may do better by translating the module to Go at build time. ncruces/go-sqlite3 moved from wazero to wasm2go for performance and start-up time. The author expects users to see no difference.

This is background for a design discussion. It is not a review finding.

References: ncruces/go-sqlite3#362 and its discussion, ncruces/go-sqlite3/discussions/361.

## Example: a guest SDK that applies these rules

The CipherStash Go SDK runs Rust guests on wazero v1.12.0. It lives in `languages/golang` in `github.com/cipherstash/stack`. It uses `WithCloseOnContextDone(true)` and a custom `MemoryAllocator` that maps, locks, and wipes memory. Its host functions call back into the guest through an `se_alloc` export.

Those choices raise the questions in sections 2, 3, 4, 7, 9, and 10. Use it as a worked case. Read its code before you copy anything.

## Limits

This skill covers how the host uses wazero. It does not review the guest's source. For a general review of a Go change, use `review-code`. `review-code` passes Go concerns to `review-golang`. That skill applies the cases here to a Go change that imports wazero.
