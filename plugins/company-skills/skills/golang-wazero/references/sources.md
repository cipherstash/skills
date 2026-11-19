# Sources for each bug class

Read this when you need the evidence behind a rule, or want to cite a report in a review. Every item was opened and read. Each fix was read where one exists. States are as found on 2026-11-19. They can change, so check a state again before you quote it.

## Contents

- 1. Panic in a host function
- 2. Concurrent calls and close during a call
- 3. Cancellation closes the module
- 4. Slices from Memory().Read
- 5. Free called with the wrong arguments
- 6. Deterministic defaults
- 7. Memory growth
- 8. CompiledModule across runtimes
- 9. Release after cancel then trap
- 10. Call into a closed module after its memory is freed
- 11. Moving away from wazero
- Notes on wazero documentation

References are `owner/repo#number`. Pull requests and issues share one number space per repository.

## 1. Panic in a host function

- 1Password/onepassword-sdk-go#288 (issue, open). A long-lived client, a DNS outage, then every call fails with `out of bounds memory access` after about 20 panics in `http_request`. A comment reproduces it with a proxy that refuses connections and traces it to the Extism host function.
- extism/go-sdk#102 (issue, open). The `http_request` host function calls `panic(err)` when the request fails. The guest's `__stack_pointer` drops by about 51,632 bytes per failed call from 1,048,576 and wraps below zero on the 20th, after which every call fails. A patch that returns status 0 and an empty response instead of panicking removed the problem in testing. The reporter notes it discards the real error. The maintainer asked for the error to go through Extism's error mechanism.
- external-secrets/external-secrets#6941 (issue, open). The operator caches the SDK client and never evicts it, so every secret stays unready until restart. A comment explains that evicting the client would not help while the SDK keeps one core for the process.
- kradalby/ts1p#2 (issue, open). Same failure under sustained uptime. The project's workaround has five parts. It retries once. It exits the process on confirmed corruption. It can recycle the instance on a schedule. It gives calls their own deadline. It counts each fault on a debug page.

## 2. Concurrent calls and close during a call

- spotify/confidence-resolver#511 (issue, closed). Exit 139 with no traceback, about 16 a week across about 150 pods. Core dumps show a nil `api.Function`. Recovery closed an instance while other resolves were mid-call.
- spotify/confidence-resolver#512 (PR, merged). `Close` now takes the call mutex. The accessor for exported functions panics with a clear message instead of returning nil and never caches nil.
- 1Password/onepassword-sdk-go#18 (PR, merged). One mutex around `plugin.Call` on the shared core.
- 1Password/onepassword-sdk-go#285 (PR, merged). One lifecycle mutex covers cold initialisation, publish, and release. Concurrent first callers then do not build duplicate runtimes.
- hoophq/hoop#1574 (PR, merged). One shared parser instance across sessions corrupted state and crashed the gateway. Fix: compile once behind `sync.Once`, instantiate one isolated instance per session, validate required exports at construction, return real errors. Tests run eight concurrent sessions under `-race`.
- daltoniam/switchboard#181 (PR, merged). A per-module call mutex around every entry point and an atomic closed flag that gives `ErrModuleClosed`. Crashes had been a nil dereference in a memory read helper and a runtime traceback fatal error.
- flipt-io/flipt-client-sdks#787 (PR, closed without merging). Quotes the wazero rule that `Call` is not goroutine-safe. It says function handles should not be stored on a shared client. Cite it for the rule, not as a fix.
- llehouerou/go-faad2#1 (PR, open). A per-decoder mutex did not cover the shared runtime. Adds a process-wide mutex held for each whole `malloc`, write, call, read, `free` sequence. Lock order is fixed.
- meokit/opus#1 (PR, open). A mutex on the shared context around encode, decode, control calls, and reset. Reproduces `fatal error: runtime: split stack overflow` with two encoders.

## 3. Cancellation closes the module

- goccy/go-graphviz#118 (issue, open). After one render is cancelled by a timeout, every later call fails with `module closed with context deadline exceeded`.
- forkcloser/go-graphviz#139 (issue, closed). In the fork the runtime has no close-on-done and one module per process. The fix is PR #200 in that fork. It honours a context until the call starts. It does not interrupt a running layout. The documentation says so.
- chennqqi/zxing#4 (issue, open). On cancel the code sets `r.module = nil`, and deferred free helpers then dereference it. Proposed: return early from the free helpers when the module is nil or closed. The runtime rebuilds on the next call.
- netsec-ethz/debuglet#175 (issue, closed) and #219 (PR, merged, included in integration PR #228). Closing a runtime during `CompileModule` on v1.12.0 panics with `assignment to entry in nil map` and ends the process. Fix: while a compile runs, `Close` only marks the run closed. The initialiser releases the runtime and compiled module exactly once afterwards and returns `net.ErrClosed`. Compile time itself is not interrupted.

## 4. Slices from Memory().Read

- flipt-io/flipt-client-sdks#761 (PR, merged). Returned memory that the guest had allocated and then freed on return. This corrupted later calls. Also fixes a double close of a channel and a blocking read that ignored shutdown.
- gen2brain/jpegxl#5 (PR, open). `img.Pix` aliased a `Memory().Read` view, and deferred frees overwrote the first pixels. Fix: `copy` into the buffer that `image.NewNRGBA64` allocates. The new test fails on main and passes with the fix.

## 5. Free called with the wrong arguments

- aquasecurity/trivy#10256 (PR, closed). `free` takes `(ptr, size)`. Two call sites passed only `ptr`, wazero returned an arity error, and `errcheck` was suppressed. Memory filled until the module failed with `module closed with exit_code(4)`. Fix: pass both arguments. Adds a signature test.
- aquasecurity/trivy#11316 (PR, open). The same bug fixed by a helper that passes pointer and size and tolerates a missing export.

## 6. Deterministic defaults

- extism/go-sdk#87 (issue, closed). A Rust guest's `rand::random` returned the same value on every call under the Go host. The fix is `WithRandSource(rand.Reader)`.
- traefik/traefik#14107 (PR, merged). Concurrent requests produced identical custom IDs. Fix: use operating-system randomness.
- crowdsecurity/crowdsec#4496 (PR, merged). Gives wazero a proper random source because the default defeated the randomness of a JavaScript obfuscator.
- e6qu/sharecrop#184 (PR, merged). Twelve pooled instances shared one predictable `crypto/rand` stream. Effects: UUID collisions, primary key violations, predictable salts, and predictable tokens. Fix: `crypto/rand.Reader` in both module configs that run a guest, and a test that needs distinct tokens from the pool.

## 7. Memory growth

- spotify/confidence-resolver#455 (issue, closed). Interleaved large state updates and small log allocations fragment the guest's allocator, so pages are added and never returned. Two related fixes are merged. #469 flushes logs before a state update. #502 skips the update when the state is unchanged.
- spotify/confidence-resolver#665 (issue, closed). In-place updates hold about 2.3 times the memory a state needs (85 MB, 140 MB, 195 MB for a 29 MB state). The issue proposes a fresh instance for each later state, with the old one closed. #666 makes that change and is open. #678 is merged. Its change keeps one copy of the state while the next loads.
- EasyTier/EasyTier#2782 (PR, merged). Guest memory moved off the Go heap with a reserved mapping that commits pages as the guest grows, plus one shared in-memory compilation cache. At 400 connections, resident memory fell from about 526 MB to about 265 MB.
- grafana/gcx#1484 (PR, merged). The same off-heap approach on Linux. Peak fell from 3,902 MiB to 2,122 MiB. The PR also makes `Close` cancel the runs and wait for them. It gives each run its own allocator and frees it itself, because of the bug in section 9. It falls back to a heap buffer when the reservation is refused.
- warpstreamlabs/bento#1087 (issue, open). A `sync.Pool` of module runners is cleared on every garbage collection. Nothing closes the runners. The patch is a bounded pool that closes what it drops. A maintainer comment lists other causes: one runtime per module, and no close on collection.

## 8. CompiledModule across runtimes

- fastschema/qjs#50 (PR, open). With wazero v1.12.0, `qjs.New()` failed with identical signatures printed as mismatched. Cause: the `CompiledModule` stores type IDs from the compiling runtime, and v1.12.0 compares them. The author closed the change after wazero fixed it on the main branch in commit 236c2458ed22 (`store should recompute type IDs at instantiation time`, wazero PR 2511). That commit is six commits after v1.12.0. v1.12.0 was the latest release when this was written.

## 9. Release after cancel then trap

- wazero/wazero#2558 (issue, open). Full reproduction and cause. See `release-on-cancel.md`.
- wazero/wazero#2561 (PR, open). Makes the closed-module release run however a call ends and lets `Close` release deferred resources once, through a compare-and-swap. Adds tests on both engines for exit, trap, and stack overflow.
- samyfodil/wazy#81 (PR, merged in the fork). The same fix in the fork, with tests for trap, `proc_exit`, host panic, stack overflow, and normal return.

## 10. Call into a closed module after its memory is freed

- wazero v1.12.0, `internal/engine/wazevo/call_engine.go`. `callEngine.Call` (lines 181 to 191) goes straight to `callWithStack`. `callWithStack` (lines 241 to 260) checks only whether the context is done.
- A test in the CipherStash Go SDK's module, run on 2026-11-19, confirmed the crash and the safe order. See `closed-module-order.md`.

## 11. Moving away from wazero

- ncruces/go-sqlite3#362 (PR, merged). Switches from wazero to wasm2go. The discussion (ncruces/go-sqlite3/discussions/361) gives two reasons: slow interpreter performance, and slow start-up on compiler targets. It also says wazero stays right for loading modules at run time.

## Notes on wazero documentation

These statements come from the v1.12.0 documentation in `api/wasm.go` and `config.go`:

- `Function.Call` is not goroutine-safe. Do not call it again before the previous call returns. Sequential calls are allowed.
- `Memory.Read` returns a view, not a copy. The view is disconnected when the memory capacity changes.
- With `WithCloseOnContextDone`, a call that ends because of the context closes the module and returns `sys.ExitError`.
- `WithRandSource` defaults to a deterministic source. The wall clock, the monotonic clock, and sleep default to fakes.
- `LinearMemory.Reallocate` may return nil on failure. `Free` releases the backing buffer.

## References checked and not cited

All references given for this skill were confirmed to exist. None was dropped.
