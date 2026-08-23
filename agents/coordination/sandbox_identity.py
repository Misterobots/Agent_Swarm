"""
sandbox_identity.py — which Docker container a sandbox tool call should target.

Mirrors tools/file_change_sink.py's threading.local() pattern exactly, because
it solves the identical problem: state that must survive the SAME
loop.run_in_executor(...) hop every DevHarness tool call goes through
(devharness_worker.py::_exec_sandbox, main.py::_exec_with_sink), by being set
at the START of the function that actually runs on the executor thread — not
by trying to propagate a value down from above. threading.local() set that way
needs no propagation at all; it's simply local to the thread already running
the call.

Callers thread an explicit container_name parameter into _exec_sandbox /
_exec_with_sink (their only two callers, and the single funnel every sandbox
tool call passes through), which call set_current_container() here before
running the tool and clear it in a finally — same shape as those functions'
existing set_file_change_sink(...)/set_file_change_sink(None) bracketing.

Falls back to the caller-supplied default (today's SANDBOX_CONTAINER env
constant) when unset, so any not-yet-migrated caller — or a caller from
before this mechanism existed — keeps working unchanged.
"""

import threading

_current = threading.local()


def set_current_container(name: str | None) -> None:
    """Set (or clear, with None) the sandbox container for the CURRENT thread only."""
    _current.name = name


def get_current_container(fallback: str) -> str:
    """Return the container name set for this thread, or `fallback` if unset."""
    return getattr(_current, "name", None) or fallback
