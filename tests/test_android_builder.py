import pytest

from agents.dev_android.builder import AndroidBuildError, _safe_component, _signed_artifact_url


def test_safe_component_rejects_path_traversal():
    assert _safe_component("project-123") == "project-123"
    assert _safe_component("owner_name") == "owner_name"
    with pytest.raises(AndroidBuildError):
        _safe_component("owner/name")


def test_safe_component_normalizes_untrusted_identifiers():
    assert _safe_component("..hidden") == "..hidden"


def test_signed_android_artifact_url_is_expiring_and_deterministic(monkeypatch):
    monkeypatch.setattr(
        "agents.dev_android.builder.ARTIFACT_SIGNING_SECRET", "test-secret"
    )
    url = _signed_artifact_url("android-job.apk")
    assert url is not None
    assert url.startswith("/v1/public-artifacts/android-job.apk?exp=")
    assert "sig=" in url
