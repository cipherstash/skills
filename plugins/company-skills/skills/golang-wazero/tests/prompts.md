# Behavior cases

This is a background convention skill: it is applied while the agent reviews or writes Go code that embeds wazero, not invoked by name. It targets wazero v1.12.0.

## Should activate

- "Review this Go change that wraps a Rust WASI module with wazero." The agent checks host functions, concurrency, context handling, memory reads, and the module config against the skill's sections.
- "Add a decoder that runs a WebAssembly build of a C library through wazero, and call it from several HTTP handlers." The agent serialises calls or uses one instance per caller, and copies bytes out of `Memory().Read`.
- "We set `WithCloseOnContextDone(true)` and added an mmap-backed memory allocator. Is this safe?" The agent raises the release-after-cancel bug and the host-side defence, with the once-only free.
- "Our Go service that uses wazero returns `module closed with context deadline exceeded` after one slow request." Incomplete request: the agent asks for the runtime config and how modules are shared before it advises.

## Should not activate

- "Write a Rust function that exports `alloc` and `free` for a WASM guest." The guest side is out of scope.
- "Run this plugin with wasmtime from Python."
- "Review this Go worker pool for goroutine leaks" in code that does not import wazero. Use the general Go review skill.

## Expected behavior

- A host function that panics on a network error is reported. The agent states the consequence: the guest stack is not restored, and the instance fails after repeated errors. It states the fix: return an error through the guest's error path, and replace an instance that has trapped.
- A shared module with a lock around only part of the `malloc`, write, call, read, `free` sequence is reported as a race. A `Close` without that lock is reported separately.
- A `Memory().Read` result that is returned or kept is reported. The fix is a copy made inside the locked section.
- A `Call` with fewer arguments than the guest export takes, or one whose error is dropped, is reported.
- A `NewModuleConfig()` without `WithRandSource` in production code is reported. A test-only use is not.
- The agent does not call a `sync.Pool` of modules a leak unless modules are dropped without `Close`.
- Each finding names the trigger and the consequence. The agent does not claim a bug from a pattern alone.
- The agent states that the wazero fix for section 9 (wazero/wazero#2561) was open when the skill was written. It checks the state before it recommends a version.
- The agent cites only references that are in `references/sources.md`.
- The agent does not invent a wazero version that contains a fix.
- The agent gives the Go module path as `github.com/tetratelabs/wazero`, not `github.com/wazero/wazero`.
- A deferred free of a host-staged buffer that runs after the allocator's `Exit` is reported. The agent states the consequence: guest code runs on unmapped memory, and the process dies with a fault that `recover` cannot catch.
- The agent proposes freeing before `Exit`, a check of `IsClosed` before each call, and a comment or test that pins the defer order. It does not say that wazero rejects a call into a closed module.
