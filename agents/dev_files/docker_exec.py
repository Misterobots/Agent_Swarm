"""
Docker exec helpers for dev_files — stub (F2).
Will implement filesystem tree reading and file R/W via docker exec.
"""
from __future__ import annotations


async def list_files(container: str, path: str) -> list[dict]:
    """List files in a container path (stub)."""
    raise NotImplementedError("Docker exec file listing not yet implemented (task F2)")


async def read_file(container: str, path: str) -> str:
    """Read a file from a container (stub)."""
    raise NotImplementedError("Docker exec file read not yet implemented (task F2)")


async def write_file(container: str, path: str, content: str) -> None:
    """Write a file in a container (stub)."""
    raise NotImplementedError("Docker exec file write not yet implemented (task F2)")
