# Step: security

Area 7, medium priority. Read this, and typescript-practices' `references/security.md`, before reviewing the change for security problems. The practices reference holds the rules and safe examples. This file says what to look for in a change, what evidence shows it, and what is not a finding.

## Contents

- [What to report](#what-to-report)
- [Tracing input](#tracing-input)
- [Evidence and tools](#evidence-and-tools)
- [Severity](#severity)
- [Not a finding](#not-a-finding)

## What to report

- **Untrusted input trusted unchecked**: a request body, file, environment variable, message, or another service's response cast to a type (`JSON.parse(text) as T`), or passed on without a schema or a type guard that checks every field. The type safety area reports the cast itself; report here what an attacker can do with the unchecked value.
- **Comparing secrets with `===` or `!==`**: a token, MAC, signature, password hash, or API key compared as strings or with a loop that stops at the first difference, instead of `crypto.timingSafeEqual` on equal-length buffers. The time the comparison takes tells an attacker how much of a guess matched.
- **Secrets in logs and errors**: a key, token, password, plaintext, or a whole request or response body passed to a logger, `console.*`, an error's message or `cause`, or `JSON.stringify` in a response. Quote the location and the kind of secret, never the secret itself.
- **Hard-coded credentials**: keys, tokens, or connection strings with a password in source, tests that reach real services, or committed configuration. A committed secret stays in history: say it must be rotated.
- **Prototype pollution**: keys from input copied one by one into a plain object, a deep merge of input, or `Object.assign` of input, so a `__proto__` key changes a prototype; values stored under input keys in a plain object instead of a `Map`; `in` or `obj[key] !== undefined` used where `Object.hasOwn` is meant.
- **Regular expressions on input**: a nested quantifier or overlapping alternatives, such as `(a+)+$`, matched against input with no length limit; a regular expression built from input without escaping.
- **Code and commands from input**: input reaching `eval`, `new Function`, `vm`, `child_process.exec`, or a shell, or an argument to `execFile` that can start with `-`.
- **Paths and URLs from input**: input used as a file path with no check for `..` or an absolute path; a redirect or `fetch` target from input with no allow-list.
- **Weak randomness**: `Math.random` for a token, key, nonce, or ID.
- **Bytes passed to native code**: a `Uint8Array` that holds a key or plaintext passed to an async native call without `slice()`, or a `subarray()` view passed where the native code reads the whole buffer.

## Tracing input

For each finding that depends on input, trace where the value comes from: a request, a webhook, a file, the environment, a documentation comment saying who supplies it, or a caller in the repository. Name the source in the finding. A value the change cannot let an attacker set, such as a constant or a value the program built itself, is not untrusted input.

## Evidence and tools

Most findings here come from reading. semgrep adds evidence when it runs, as `checks.md` describes: its `p/typescript` and `p/javascript` rulesets report some uses of `eval`, `child_process`, unsafe regular expressions, and hard-coded secrets. Quote the rule ID with the finding. It does not trace input across functions, so a clean run says little: report what reading finds. A `// nosemgrep` comment with a reason that holds is not a finding. osv-scanner's results belong to the dependency management area.

If semgrep did not run, record it under checks as not run and review by reading.

## Severity

- `critical`: the review traces a realistic attacker-controlled input, or an exposed network path, to the problem: code or a command run from a request, a path that reads outside its directory, prototype pollution of `Object.prototype` from a request body, a real credential committed.
- `major`: the problem is real, but the review cannot show who controls the input, or using it takes effort the review cannot show is practical. A secret compared with `===` or `!==` against a value a caller sends is `major`: the attacker needs many timed requests, and the review rarely shows them reaching the secret.
- `minor`: a broken rule with no demonstrated exposure, such as `Math.random` for a value that is not a secret but is named like one.

## Not a finding

- Fake credentials in a test that talks only to a local test server.
- A `// nosemgrep` suppression with a reason that holds.
- `===` on values that are not secret, such as an ID or a status.
- A regular expression on input whose length the code limits first, or with no repeated group.
- A theoretical attack with no path from input to the code.
