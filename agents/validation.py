import sys

staged = "/workspace/codex-validation-full-20260824/agents"
sys.path.insert(0, staged)

import agents
agents.__path__.insert(0, staged)
import agents.coordination
agents.coordination.__path__.insert(0, staged + "/coordination")
import agents.dev_harness
agents.dev_harness.__path__.insert(0, staged + "/dev_harness")
import agents.main
import agents.coordination.orchestrator
import agents.coordination.workspace_ops
import agents.coordination.workspace_lifecycle
import agents.dev_harness.loop
import agents.dev_harness.permissions
import agents.dev_harness.approval_service
import agents.dev_harness.replay_policy

print("staged_overlay_imports=ok")
