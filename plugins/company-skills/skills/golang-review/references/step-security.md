# Step: security

Area 6, medium priority. Read this, and golang-practices' `references/security.md`, before reviewing the change for security problems. The practices reference holds the rules and safe examples. This file says what to look for in a change, what evidence shows it, and what is not a finding.

## Contents

- [What to report](#what-to-report)
- [Tracing input](#tracing-input)
- [Evidence and tools](#evidence-and-tools)
- [Severity](#severity)
- [Not a finding](#not-a-finding)

## What to report

- **Skipped TLS verification**: `InsecureSkipVerify: true` outside a test, or a custom `VerifyPeerCertificate` that accepts any certificate. Anyone on the network path can read and change the traffic.
- **Hard-coded credentials**: passwords, API keys, tokens, private keys, or connection strings with a password in source, tests that reach real services, or committed config. Quote the location and the kind of secret, never the secret itself. A committed secret stays in history: say it must be rotated.
- **Secrets in logs and errors**: a secret, or a whole config or request struct that holds one, passed to a logger, `fmt.Errorf`, or a panic.
- **SQL built from input**: a query built with `+`, `fmt.Sprintf`, or `strings.Builder` from any value that is not a constant, instead of placeholders and arguments.
- **Unsanitised input**: a value from outside the process used unchecked as a file path (`../` traversal), in a shell (`sh -c`, or an argument that can start with `-`), in HTML through `text/template` or `template.HTML`, in a redirect target or URL, or as a size or count with no limit, such as a request body read with no `http.MaxBytesReader`.
- **Weak randomness and comparison**: `math/rand` for tokens, keys, or nonces; `==` to compare secrets; MD5, SHA-1, or plain SHA-256 for passwords or signatures.
- **Servers with no timeouts**: an `http.Server` with no `ReadHeaderTimeout`, or `http.ListenAndServe` on a public port.

## Tracing input

For each finding that depends on input, trace where the value comes from: a request, a file, the environment, a doc comment saying who supplies it, or a caller in the repository. Name the source in the finding. A value the change cannot let an attacker set, such as a constant or a value the program built itself, is not unsanitised input.

## Evidence and tools

Most findings here come from reading. Tools add evidence when they are installed, as `checks.md` describes:

- `gosec ./<packages>`, or `golangci-lint run` with `gosec` enabled when the repository configures it. Its rule IDs map to this area: G402 TLS, G101 credentials, G201 and G202 SQL, G304 file paths, G404 weak random, G112 server timeouts. Quote the rule ID with the finding. A `#nosec` or `//nolint:gosec` comment with a reason that holds is not a finding.
- `go vet` finds none of these. A clean vet says nothing about security.

If no security linter is installed, record it under checks as not run and review by reading.

## Severity

- `critical`: the review traces a realistic attacker-controlled input, or an exposed network path, to the problem: SQL injection from a request, a path traversal that reads outside a directory, verification skipped on a production client, a real credential committed.
- `major`: the problem is real, but the review cannot show who controls the input, or the exposure is limited, such as a server with no header timeout.
- `minor`: a broken rule with no demonstrated exposure, such as `math/rand` for a value that is not a secret but is named like one.

## Not a finding

- `InsecureSkipVerify` or fake credentials in a test that talks only to a local test server.
- A `#nosec` suppression with a reason that holds.
- SQL built from constants only, such as a fixed table name chosen from a closed list.
- A theoretical attack with no path from input to the code.
