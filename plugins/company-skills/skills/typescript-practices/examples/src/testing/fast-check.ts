import { fc } from "@fast-check/vitest";

// Pull request CI: the same inputs on every run, so a pull request fails
// only for its own change. Property tests import fc and test from here.
fc.configureGlobal({ seed: 42, numRuns: 100 });

export { fc, test } from "@fast-check/vitest";
