# Security

This reference targets Python 3.12. Read the project's `requires-python` first. A rule that needs a later version names it. Skip it when the project's lowest supported version is below it. The examples are in the [examples project](../examples/pyproject.toml), where CI runs the check suite over them.

ruff's `S` rules, semgrep's `p/python` rules, and pip-audit check much of this, as [checks.md](checks.md) says. They cannot see where data comes from, so follow each rule whether or not a tool flags the line.

## Rules

- Pass every value into SQL as a query parameter. Never build a query with an f-string, `%`, `+`, or `.format`, which ruff's `S608` flags. A table or column name cannot be a parameter, so pick it from a fixed set in your code.
- Make tokens, keys, nonces, and passwords with `secrets`, never `random`, which ruff's `S311` flags. Name the length in bytes: `secrets.token_bytes(32)`. A call with no length takes a default that can change.
- Compare a secret with `hmac.compare_digest`, never `==`, which returns sooner the sooner the values differ.
- Run a program with `subprocess.run` and a list of arguments. Never pass `shell=True` or call `os.system`. Put `--` before an argument that comes from outside, so a value that starts with `-` is not read as an option. Pass `check=True`.
- Never load untrusted input with `pickle`, `marshal` or `shelve`, which can run any code, or `yaml.load`, which can build any object. Use `json`, or `yaml.safe_load`. Never pass untrusted input to `eval`, `exec` or `compile`. For a Python literal, use `ast.literal_eval`.
- Keep secrets out of `repr`, `str`, logs, exception messages, and tracebacks. Hold each one in a type whose `repr` hides the value, and read the value only where it is used. A `@dataclass` field that holds a secret needs `field(repr=False)`.
- Never log a request body, a header, or a whole configuration object, which can hold a token. Log the fields you need by name.
- Read secrets from the environment or a secret store, never from source. ruff's `S105` and `S106` flag a literal that looks like a password.
- Set a `timeout` on every network call. A call with none can wait for ever.
- Verify TLS. Never pass `verify=False`.
- Extract an archive with `tarfile`'s `filter="data"`, so a member cannot write outside the target directory.

## Examples

The input is a value in the query, never part of its text. From [`security.py`](../examples/src/practices/security.py):

```python
def find_user(conn: sqlite3.Connection, email: str) -> User | None:
    query = "SELECT id, name, email FROM users WHERE email = ?"
    row = conn.execute(query, (email,)).fetchone()
    return None if row is None else User(*row)
```

`TOKEN_BYTES` is 32. From [`security.py`](../examples/src/practices/security.py):

```python
def new_token() -> bytes:
    return secrets.token_bytes(TOKEN_BYTES)


def token_matches(given: bytes, expected: bytes) -> bool:
    return hmac.compare_digest(given, expected)
```

ruff's `S603` flags every `subprocess` call, so the `noqa` says why this one is safe. The full path from `shutil.which` keeps `S607` quiet. From [`security.py`](../examples/src/practices/security.py):

```python
def blob_id(path: Path) -> str:
    """Return the Git blob ID of the file at path."""
    git = shutil.which("git")
    if git is None:
        raise MissingToolError("git")
    result = subprocess.run(  # noqa: S603  # An argument list with no shell.
        [git, "hash-object", "--", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()
```

From [`security.py`](../examples/src/practices/security.py):

```python
class Secret:
    """A value that never appears in repr, str, or a log line."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def __repr__(self) -> str:
        return "Secret('[REDACTED]')"

    __str__ = __repr__

    def reveal(self) -> str:
        return self._value
```
