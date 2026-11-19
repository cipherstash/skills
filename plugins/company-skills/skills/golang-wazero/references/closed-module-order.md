# Calling a closed module after its memory is freed

If an allocator unmaps guest memory, and your code calls guest exports around that point, read this file. It expands section 10 of `SKILL.md`.

## Contents

- The sequence
- What the test does
- Results
- Cautions for your own test

## The sequence

1. A call into the guest starts. The allocator marks it in flight with `Enter`.
2. The call's context ends during a host function. wazero's watcher closes the module and defers the release of its resources.
3. The guest re-enters or returns. wazero asks the allocator to `Free` the memory. The allocator holds the request back, because a call is in flight.
4. The call ends. `Exit` performs the held `Free`. The memory is now wiped and unmapped.
5. Code that runs after step 4 calls an export, such as `se_dealloc` to free a staged buffer.

wazero v1.12.0 does not check for a closed module when a call starts. The guest runs on unmapped memory and the process dies with a fault.

Step 5 is the whole bug. Freeing the staged buffer before step 4 is safe, because the memory is still mapped.

## What the test does

The test is in the CipherStash Go SDK's module, in a copy outside the repository. It has two cases. Each runs in its own process, because the test binary re-runs itself with `-test.run` and an environment variable. A leaked memory lock then cannot break the next case.

Both cases stage a buffer by hand and call `se_cipher_init`. A harness cancels the call's context at the first host function and waits for the module to close. The cases differ in one line.

- **Wrong order.** The test calls `Exit`, then frees the staged buffer.
- **Correct order.** The test frees the staged buffer, then calls `Exit`.

The wrong-order parent asserts that the child exited with a fatal runtime error. The correct-order parent asserts that the child passed. In the child, it asserts that the module is closed, that the call returned an error, and that `Allocator.IsFreed()` is true after `Client.Close`.

## Results

Each case ran at least 8 times in its own process on Linux with wazero v1.12.0 and Go 1.26.10.

- **Wrong order.** The process died every time. Most deaths were `unexpected fault address` and `fatal error: fault [signal SIGSEGV]`. A few were `fatal error: runtime: split stack overflow`. Both come from the same fault in compiled code, and `recover` does not catch either. A test that checks for one message only will fail now and then. Check for a fatal runtime error.
- **Correct order.** No crash in any run. The module was closed. The memory was freed after `Client.Close`.

## Cautions for your own test

- Run each case in its own process. A crash ends the process. Leaked locked memory stays locked until the process exits, and `RLIMIT_MEMLOCK` can be as low as 8 MiB.
- Skip the wrong-order case when the allocator falls back to a heap buffer. The memory then stays valid and nothing faults.
- Free with `context.Background()` in the wrong-order case. A context that is already done makes wazero close the module and return an error before it runs guest code. That would hide the bug.
- Wait for the module to close after the cancel. The watcher closes it on another goroutine.
