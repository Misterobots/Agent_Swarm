# router.py — backward-compatibility shim
# This module was renamed to church.py (Router → Church, Pioneer naming scheme).
# detect_intent was always in dispatcher.py; both are re-exported here so any
# remaining references (verify scripts, system_test, etc.) continue to work.
from church import chat_swarm
from dispatcher import detect_intent

__all__ = [
    "chat_swarm",
    "detect_intent",
]
