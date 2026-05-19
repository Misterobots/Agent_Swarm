# coordinator.py — backward-compatibility shim
# This module was renamed to lamport.py as part of the Pioneer naming scheme.
# This shim re-exports everything so any remaining references (cached .pyc,
# container volumes, tests, or external imports) continue to work.
from lamport import (
    _team_store,
    _team_clear,
    WorkerState,
    WorkerInfo,
    CoordinatorSession,
    coordinate_task,
)

__all__ = [
    "_team_store",
    "_team_clear",
    "WorkerState",
    "WorkerInfo",
    "CoordinatorSession",
    "coordinate_task",
]
