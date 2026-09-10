from dev_harness.workspace import session_workspace_spec


def test_desktop_workspace_overrides_live_repo_default():
    assert session_workspace_spec(
        r"C:\Users\panca\Documents\Github\Dauntless_Revival", "live_repo"
    ) == ("desktop_local", r"C:\Users\panca\Documents\Github\Dauntless_Revival")


def test_unselected_workspace_keeps_legacy_project_mode():
    assert session_workspace_spec(None, "live_repo") == ("live_repo", None)
    assert session_workspace_spec("", "git") == ("ephemeral", None)
