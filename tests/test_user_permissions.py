from agents.user_permissions import FEATURES, UserPermissionStore


def test_missing_policy_preserves_existing_access(tmp_path):
    store = UserPermissionStore(str(tmp_path / "permissions.json"))

    policy = store.get("alice")

    assert policy["configured"] is False
    assert policy["allowed_models"] is None
    assert all(policy["features"].values())
    assert policy["features"]["planning"] is True
    assert policy["features"]["swarm"] is True
    assert store.model_allowed("alice", "qwen3:14b")


def test_explicit_policy_enforces_models_and_features(tmp_path):
    store = UserPermissionStore(str(tmp_path / "permissions.json"))
    features = {key: True for key in FEATURES}
    features["code"] = False

    saved = store.set("alice", ["qwen3:8b", "qwen3:8b"], features)

    assert saved["configured"] is True
    assert saved["allowed_models"] == ["qwen3:8b"]
    assert store.model_allowed("alice", "qwen3:8b")
    assert not store.model_allowed("alice", "qwen3:14b")
    assert not store.feature_allowed("alice", "code")
    assert store.feature_allowed("alice", "chat")


def test_reset_restores_inherited_access(tmp_path):
    store = UserPermissionStore(str(tmp_path / "permissions.json"))
    store.set("alice", [], {key: False for key in FEATURES})

    assert store.delete("alice") is True
    assert store.get("alice")["configured"] is False
    assert store.feature_allowed("alice", "chat")
