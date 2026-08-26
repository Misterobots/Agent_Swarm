from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents"))

from publish_state import consume_push_confirm


class FakeRedis:
    def __init__(self, value):
        self.value = value

    def getdel(self, _key):
        value, self.value = self.value, None
        return value

    def get(self, _key):
        return self.value

    def delete(self, _key):
        self.value = None


def test_confirm_token_is_single_use_and_accepts_bytes():
    redis = FakeRedis(b"token-1")
    assert consume_push_confirm(redis, "confirm", "token-1")
    assert not consume_push_confirm(redis, "confirm", "token-1")


def test_invalid_confirm_token_does_not_consume_valid_token():
    redis = FakeRedis("token-2")
    assert not consume_push_confirm(redis, "confirm", "wrong")
    assert redis.value == "token-2"
