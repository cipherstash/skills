# Testing

How to test TypeScript: Vitest for behaviour, `expectTypeOf` for types, and fast-check property tests for code that parses untrusted input. The examples target TypeScript 7.0 and Node 24, with the compiler settings that [checks.md](checks.md) requires. They are quoted from the [examples package](../examples/package.json), where CI type-checks, lints, and tests them.

## Vitest

- Put a module's tests beside it, in `<module>.test.ts`. CI runs them with `vitest run --coverage`, as [checks.md](checks.md) says.
- Import `test`, `expect`, and `vi` from `vitest`. Do not turn on Vitest's globals.
- Test what a caller can see, through the module's exports. A test that breaks when the code is restructured but behaves the same is testing the wrong thing.
- Give each test a name that states the behaviour, such as `"returns each expected failure as a failure"`. Test one behaviour in each.
- Take each expected value from somewhere other than the code under test: a literal, a worked example, or the specification. An expected value computed the way the code computes it can never fail.
- `await` every promise in a test. Test a rejection with `await expect(promise).rejects`, and an expected failure by comparing the whole result.
- Mock only what the process does not own: the network, the clock, and other services. Use `vi.useFakeTimers()` for time. Prefer a real module, or a small fake passed in as an argument, to `vi.mock`.
- An integration test that needs a service, a key, or a credential fails with a message naming what is missing when it is not configured. It never passes by skipping itself.
- Do not write tests for input the type system already rules out. Do test the runtime checks at a boundary, where the types cannot help.
- Coverage is a figure to read, not a target. There is no threshold.

## Type tests

A type test checks what the compiler infers. Write one for an exported generic, conditional, or mapped type, and for narrowing a caller relies on. `expectTypeOf` from Vitest does nothing at run time. `tsc --noEmit` checks it, because the test files are in a `tsconfig` that the suite type-checks. From [`src/error-handling/result.test.ts`](../examples/src/error-handling/result.test.ts):

```ts
test("types data as a number once failure is ruled out", () => {
  const result = parsePort("443");
  expectTypeOf(result.data).toEqualTypeOf<number | undefined>();
  if (!result.failure) {
    expectTypeOf(result.data).toEqualTypeOf<number>();
  }
});
```

- Use `toEqualTypeOf` for an exact type, and `toExtend` when the type only needs to be assignable. Use `// @ts-expect-error` on a line that must not compile.
- A type test in its own `*.test-d.ts` file needs `vitest --typecheck` to run it. Keep type tests in `*.test.ts` files, so `tsc` checks them.

## Property tests for untrusted input

A function that parses or decodes untrusted input has a fast-check property test, written with `@fast-check/vitest`. Untrusted input is bytes from outside the process, such as a request body, a file, or a message. A property test calls the function with many generated inputs and checks a statement that holds for all of them. From [`src/testing/property.test.ts`](../examples/src/testing/property.test.ts):

```ts
test.prop([fc.oneof(fc.string(), fc.json())])(
  "returns data or a failure for any body, and never throws",
  (body) => {
    const result = parseKeyRequest(body);
    expect(result.data ?? result.failure).toBeDefined();
  },
);
```

- Check that the function never throws for any input, or throws only the errors it documents.
- Check a round trip where one exists: whatever the parser accepts, it gives back unchanged, and whatever the encoder writes, the decoder reads. From [`src/testing/property.test.ts`](../examples/src/testing/property.test.ts):

```ts
test.prop([
  fc.record({ keyId: fc.string({ minLength: 1 }), context: fc.string() }),
])("accepts every valid request", (request) => {
  expect(parseKeyRequest(JSON.stringify(request))).toEqual({ data: request });
});
```

- Generate input close to the real format, such as `fc.json()` or a record of the expected fields, as well as arbitrary strings or bytes with `fc.string()` and `fc.uint8Array()`. Input that is only random rarely gets past the first check.

In pull request CI, every property test runs with a fixed seed and a set number of runs, so a pull request fails only for its own change. Set both once, in a module that configures fast-check and re-exports `fc` and `test`. Every property test imports them from it, as `import { fc, test } from "./fast-check.js"`, so none can run unconfigured. From [`src/testing/fast-check.ts`](../examples/src/testing/fast-check.ts):

```ts
// Pull request CI: the same inputs on every run, so a pull request fails
// only for its own change. Property tests import fc and test from here.
fc.configureGlobal({ seed: 42, numRuns: 100 });
```

- Do not set `seed` or `numRuns` in a single test, so that one change moves them for every test.
- Leave the module out of the build, with the tests.
- Run random seeds and more runs in a scheduled job, never in pull request CI. When a run fails, fast-check prints the seed and the path of the failing input. Add that input to a plain test, then fix the code.
- A repository that already has a Vitest configuration may call `fc.configureGlobal` from a file in its `setupFiles` instead. The configuration and its setup files run code during a test, so they are on the execution surface that [checks.md](checks.md) lists.
