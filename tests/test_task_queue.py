from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from coordination import task_queue


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.lists = {}

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    def get(self, key):
        return self.values.get(key)

    def delete(self, *keys):
        removed = 0
        for key in keys:
            removed += int(self.values.pop(key, None) is not None)
            removed += int(self.lists.pop(key, None) is not None)
        return removed

    def rpush(self, key, value):
        self.lists.setdefault(key, []).append(value)
        return len(self.lists[key])

    def llen(self, key):
        return len(self.lists.get(key, []))

    def lrem(self, key, count, value):
        items = self.lists.get(key, [])
        before = len(items)
        self.lists[key] = [item for item in items if item != value]
        return before - len(self.lists[key])

    def lpop(self, key):
        items = self.lists.get(key, [])
        return items.pop(0) if items else None

    def scan_iter(self, match=None):
        keys = set(self.values) | set(self.lists)
        prefix = match[:-1] if match and match.endswith("*") else match
        return (key for key in keys if not prefix or key.startswith(prefix))


def test_project_scopes_do_not_share_lock_or_fifo(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(task_queue, "get_redis_client", lambda: redis)

    assert task_queue.try_acquire("run-a", "project-a")
    assert task_queue.try_acquire("run-b", "project-b")
    assert not task_queue.try_acquire("run-a-2", "project-a")

    assert task_queue.enqueue("queued-a", "project-a") == 1
    assert task_queue.enqueue("queued-b", "project-b") == 1
    assert task_queue.pop_next("project-a") == "queued-a"
    assert task_queue.pop_next("project-b") == "queued-b"


def test_default_scope_remains_serialized(monkeypatch):
    redis = FakeRedis()
    monkeypatch.setattr(task_queue, "get_redis_client", lambda: redis)

    assert task_queue.try_acquire("run-1")
    assert not task_queue.try_acquire("run-2")
    task_queue.release("run-1")
    assert task_queue.try_acquire("run-2")
