import os


WORKSPACE_ANCHORS = {
    "delivered_artifacts",
    "training_data",
    "training_output",
    "workflow_state",
    "docs",
    "output",
}


def resolve_workspace_path(candidate_path: str) -> str:
    if not candidate_path:
        return candidate_path

    if os.path.exists(candidate_path):
        return candidate_path

    normalized = candidate_path.replace("\\", "/")
    if os.path.exists(normalized):
        return normalized

    workspace_root = os.getenv("WORKSPACE_ROOT", "/workspace")
    path_parts = [part for part in normalized.split("/") if part]

    for index, part in enumerate(path_parts):
        if part in WORKSPACE_ANCHORS:
            mapped = os.path.join(workspace_root, *path_parts[index:])
            if os.path.exists(mapped):
                return mapped

    return candidate_path