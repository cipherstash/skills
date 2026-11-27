# Step: error handling

Area 1, high priority. Read this, and python-practices' `references/errors.md`, before reviewing the change's error handling. When the change is in a pyo3 or maturin package, also read `references/native-extensions.md`: a Rust panic or error reaches Python as an exception. The practices reference holds the rules and working examples. This file says what to look for in a change, what evidence shows it, and what is not a finding.

## Contents

- [A lost cause](#a-lost-cause)
- [A swallowed cancellation](#a-swallowed-cancellation)
- [A bare or broad except that hides failures](#a-bare-or-broad-except-that-hides-failures)
- [A library that configures logging](#a-library-that-configures-logging)
- [Other error-handling defects](#other-error-handling-defects)
- [Evidence](#evidence)
- [Version-sensitive rules](#version-sensitive-rules)
- [Not a finding](#not-a-finding)

## A lost cause

Look in every changed `except` block for a `raise` of a new error with no `from`, such as `raise StorageError(path)` inside `except OSError:`. Python still prints the first error as context. But the new error has no `__cause__`. The traceback then says "During handling of the above exception, another exception occurred". That reads as a second bug in the handler.

Code that reads `error.__cause__`, such as a retry policy or an error report, finds nothing. If the change dropped a `from error` that the base had, say so: it is part of the cause.

Cite the practices rule: inside `except`, raise a new error with `raise NewError(...) from error`. This is `minor` when nothing reads the cause, and `major` when code in the repository reads `__cause__` or matches on it. `raise ... from None` is not a lost cause when the reason is given: it hides a cause on purpose.

## A swallowed cancellation

`asyncio.CancelledError` is a `BaseException`. Look for changed code that catches it and does not re-raise it:

- `except asyncio.CancelledError:` or `except BaseException:` whose block ends without `raise`;
- a bare `except:`, since it catches cancellation too;
- a `return`, `break`, or `continue` in a `finally` block of a coroutine. It drops whatever was being raised, cancellation included;
- `asyncio.shield`, `contextlib.suppress(asyncio.CancelledError)`, or a callback that discards a task's cancellation.

The trigger is a cancellation: a `TaskGroup` sibling failing, an `asyncio.timeout` running out, or a shutdown. The task keeps running after it was cancelled. A `TaskGroup` waits for it, `asyncio.timeout` never raises `TimeoutError`, and a shutdown hangs. This is `major`.

## A bare or broad except that hides failures

Look for a changed `except:`, `except BaseException:`, or `except Exception:` that does not re-raise. A broad catch is allowed only at a boundary, such as a request handler, a worker loop, or a command's entry point. Also look for a narrow `except` around a whole block where only one call can raise it, and for `contextlib.suppress` of a broad type.

Follow what the code does when the call fails for an unexpected reason, such as a `KeyError` from a typo. The consequence is a default value, a skipped record, or a success result where the caller needed the failure. This is `major` when the review shows the wrong result reaching a caller. It is `minor` when the block only logs and the caller still gets the failure. A bare `except:` also catches `KeyboardInterrupt` and `SystemExit`, so Ctrl-C no longer stops the program.

## A library that configures logging

In code that other code imports, such as a package under `src/`, look for a changed line that configures the application's logging:

- `logging.basicConfig(...)`, `logging.config.dictConfig(...)`, or `logging.config.fileConfig(...)`;
- a handler other than `logging.NullHandler` added to any logger, or a level set on the root logger or the package's top-level logger;
- `logging.disable(...)`, or `logging.captureWarnings(True)`.

Importing the library then changes every log line of the application. Output is duplicated, takes a format the application did not choose, or is lost below a level the library set. Cite the practices rule: a library adds only a `NullHandler` to its package logger. This is `minor`, unless the review shows logs lost or a secret logged. A script or a command's entry point may configure logging; that is not a finding.

## Other error-handling defects

The practices reference also covers these. Report them when the change introduces them:

- An error logged and then raised again, so the same failure is reported twice.
- `logger.exception(...)` outside an `except` block. It logs `NoneType: None` in place of a traceback.
- `raise error` where a bare `raise` was meant. It adds the handler's line to the traceback.
- An `ExceptionGroup`, such as one from `asyncio.TaskGroup`, caught with `except` where `except*` was meant, so the handler never matches the errors inside it.

## Evidence

ruff gives evidence for several of these, with the rule families python-practices lists:

- `B904`: a raise without `from` inside `except`;
- `E722`: a bare `except:`;
- `BLE001`: a broad `except`;
- `S110` and `S112`: an `except` whose block is only `pass` or `continue`;
- `TRY400`: `logger.error` where `logger.exception` was meant;
- `ASYNC`: some cancellation mistakes.

Run ruff as `checks.md` runs it, and quote the code and line. No tool finds a `CancelledError` caught by name and swallowed. No tool finds a library that configures logging. For those, quote the lines read and the path that shows the consequence.

## Version-sensitive rules

Read the module's floor from step 3 before you flag a rule or suggest a fix. `ExceptionGroup`, `except*`, `asyncio.TaskGroup`, `asyncio.timeout`, and `BaseException.add_note` need Python 3.11. Below 3.11, flag none of the rules that need them, and suggest no fix that uses them.

## Not a finding

- A broad `except` at a boundary that logs the traceback with `logger.exception` and goes on, such as a worker loop that outlives one bad job.
- `raise ... from None` with a reason in a comment or the message.
- A `CancelledError` caught to clean up and then re-raised with a bare `raise`.
- Logging configured in a script, a test, or the application's entry point.
- Error message wording or style. That belongs to the naming and style area, not this one.
- Error handling in code the change neither adds nor makes reachable.
