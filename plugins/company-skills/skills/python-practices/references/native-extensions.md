# Native extensions with pyo3 and maturin

This reference targets Python 3.12. Read the project's `requires-python` first. A rule that needs a later version names it. Skip it when the project's lowest supported version is below it. It covers a Python package whose core is Rust, bound with pyo3 and built with maturin. It states its rules in prose and has no examples, so this repository's Python CI needs no Rust toolchain.

**Labelled example:** the cipherstash/stack Python SDK (cipherstash/stack#1284) is a package of this kind, a Python API over CipherStash's Rust encryption engine. Read its layout as one way to apply these rules, not as a rule of its own.

The Python side follows every other python-practices reference. The Rust side follows the company Rust rules: `rust-sdk-dx` for its API, `rust-security` for keys and secrets, and `rust-testing` for its tests.

## Wheels and the version floor

- Build abi3 wheels, which use Python's stable ABI, so one wheel per platform runs on every Python from its floor up. Turn on pyo3's `abi3-pyXY` feature for the lowest version in `requires-python`: `abi3-py312` for `">=3.12"`. A higher feature than the floor makes a wheel that older interpreters refuse. A lower one gives up stable-ABI functions the code could use.
- Raise the abi3 feature and `requires-python` together, in one change, and treat it as a breaking change, as [project-structure.md](project-structure.md) says.
- The free-threaded build has no stable ABI before Python 3.15, so a free-threaded wheel is a separate, version-specific wheel. Build one only when users need it.
- Build wheels for every platform you support in CI, and publish them with a source distribution. Test each wheel by installing it, not the source tree, and running the Python tests against it.

## Types

- A compiled module has no annotations that mypy can read. Ship a `.pyi` stub for it, with full annotations under the rules in [typing.md](typing.md), and a `py.typed` file. With maturin's mixed layout, put both in the Python package directory, next to the `.py` files, and maturin includes them in the wheel.
- Keep the stub in step with the Rust signatures. Check it with `mypy --strict` over the tests, which call the real module through the stub. A test that passes while mypy fails means the stub is wrong.
- Map each Rust error type to a Python exception class, defined once, with a base class for the package, as [errors.md](errors.md) says. Never let a Rust panic reach Python as the result of a bad input: return an error instead.

## A locked build

- Pin maturin to an exact version in `[build-system] requires`, and in the `dev` dependency group, so the committed `uv.lock` fixes it.
- In CI, install the locked tools with `uv sync --locked`, then build with build isolation off, such as `uv build --no-build-isolation` or `maturin build` in that environment. Build isolation resolves the backend afresh from the index on every build, so the backend that builds the release would not be the locked one.
- Commit `Cargo.lock`, and build with `--locked`, so the Rust dependencies are fixed too.
- Building the package runs `build.rs` and procedural macros from the Rust dependency tree. That is part of the Python execution surface, as [checks.md](checks.md#execution-surface) lists.

## The GIL and threads

- Release the GIL around Rust work that does not touch Python objects and takes more than a few microseconds, such as encryption or I/O, so other Python threads can run. In pyo3 0.26 and later, call `Python::detach`. Before 0.26 it is `allow_threads`. Copy the inputs out of Python objects before releasing the GIL, and take it back before building the result.
- Never hold a Rust lock while calling back into Python. The callback can wait for the GIL while another thread that holds the GIL waits for the lock.
- Declare free-threading support only after checking that no Rust state shared between calls relies on the GIL. In pyo3, set `gil_used = false` on the `#[pymodule]`. Without it, importing the module on the free-threaded build turns the GIL back on.

## Untrusted input

- Fuzz the Rust functions that parse or decode untrusted input on the Rust side, under the Rust rules, with `cargo fuzz`. Bytes reach that code from Python unchanged, so a Rust fuzz target covers it more deeply than a Python test.
- Add a Hypothesis `@given` test on the Python side too, as [testing.md](testing.md) says, to check the conversion between Python and Rust types and the exceptions the binding raises.
