# Step: security

Area 7, medium priority. Read this, and python-practices' `references/security.md`, before reviewing the change for security problems. The practices reference holds the rules and safe examples. This file says what to look for in a change, what evidence shows it, and what is not a finding.

## Contents

- [What to report](#what-to-report)
- [Tracing input](#tracing-input)
- [Evidence and tools](#evidence-and-tools)
- [Severity](#severity)
- [Version-sensitive rules](#version-sensitive-rules)
- [Not a finding](#not-a-finding)

## What to report

- **Skipped TLS verification**, outside a test. Anyone on the network path can read and change the traffic. Look for:
  - `verify=False` on an `httpx` or `requests` call or client;
  - `ssl._create_unverified_context`;
  - an `SSLContext` with `check_hostname = False` or `CERT_NONE`.
- **Hard-coded credentials**: passwords, API keys, tokens, private keys, or connection strings with a password. Look in source, in committed config, and in tests that reach real services. Quote the location and the kind of secret, never the secret itself. A committed secret stays in history: say it must be rotated.
- **Secrets in `repr`, logs, and errors**:
  - a secret in a field with no `field(repr=False)` or redacting `repr`;
  - a secret passed to a logger, an exception message, or `print`;
  - a whole request, header map, or configuration object logged.
- **SQL built from input**: a query built from a value that is not a constant, with an f-string, `%`, `+`, or `.format`. Query parameters were meant.
- **Code or objects from untrusted input**: a value from outside the process passed to any of these:
  - `pickle`, `marshal`, or `shelve`;
  - `yaml.load` with an unsafe loader;
  - `eval`, `exec`, or `compile`.
- **Programs and paths**:
  - `shell=True`, `os.system`, or `os.popen`;
  - an argument from outside that can start with `-`, with no `--` before it;
  - a path from outside, with no check that it stays in its directory;
  - `tarfile` or `zipfile` extraction with no `filter="data"`.
- **Weak randomness and comparison**:
  - `random` for tokens, keys, nonces, or passwords;
  - `secrets` with no explicit length;
  - `==` to compare secrets, where `hmac.compare_digest` was meant;
  - MD5, SHA-1, or plain SHA-256 for passwords.
- **Network calls with no timeout**, on a client that has none by default, such as `requests` or `urllib.request.urlopen`.

## Tracing input

For each finding that depends on input, trace where the value comes from. It can come from a request, a file, the network, the environment, or a caller in the repository. A docstring may say who supplies it. Name the source in the finding.

A value the change cannot let an attacker set is not untrusted input. Examples are a constant, or a value the program built itself.

## Evidence and tools

Most findings here come from reading. Tools add evidence, as `checks.md` describes:

- ruff's `S` rules run with the suite's families. Quote the rule ID with the finding. These rules map to this area:
  - `S105` and `S106` for credentials, and `S501` for TLS verification;
  - `S301` for pickle, `S307` for eval, and `S506` for unsafe YAML;
  - `S311` for weak random, and `S324` for weak hashes;
  - `S602` and `S605` for a shell, and `S608` for SQL;
  - `S113` for a `requests` call with no timeout, and `S202` for tar extraction.
- `S608` looks only at a string that reads like SQL. It misses a query built in parts and returned. Only reading finds that.
- A `# noqa: S<code>` is not a finding when its reason is true.
- semgrep with `p/python`, only when it is installed and the user allows the network. Quote its rule ID.
- `pip-audit`, for a dependency with a known vulnerability. That finding goes under dependency management.
- mypy finds none of these. A clean mypy run says nothing about security.

## Severity

- `critical`: the review traces an input an attacker can set, or an exposed network path, to the problem. What comes through is stored, run, or sent on. Examples:
  - SQL injection from a request;
  - a path traversal that reads outside a directory;
  - `pickle` of a network message;
  - TLS checks off on a client whose responses the program saves or acts on;
  - a real credential committed.
- `major`: the problem is real. But the review cannot show who controls the input, or the exposure is limited, such as a network call with no timeout.
- `minor`: a broken rule with no shown exposure. An example is `random` for a value named like a secret that is not one.

## Version-sensitive rules

Read the module's floor from step 3 before you flag a rule or suggest a fix. `tarfile`'s `filter="data"` needs Python 3.12, or a 3.8 to 3.11 security release that added it. Below that, suggest checking each member's path instead.

## Not a finding

- `verify=False` or fake credentials in a test that talks only to a local test server.
- A `# noqa` on an `S` rule, when its reason is true.
- SQL built from constants only, such as a table name chosen from a fixed set in the code.
- `subprocess.run` with an argument list, no shell, and `--` before outside values.
- A theoretical attack with no path from input to the code.
