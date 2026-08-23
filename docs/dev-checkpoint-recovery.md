# DevHarness checkpoint recovery

Checkpoint recovery is an explicit, owner-scoped API flow. It is intentionally
at-least-once for a tool whose process may have died after the side effect
started: inspect the workspace before replaying a mutating command.

## 1. Inspect the checkpoint

Use the same authenticated session and `X-authentik-uid` identity that started
the DevHarness session:

```bash
curl -H "X-authentik-uid: <uid>" \
  "<agent-runtime>/api/v1/dev/checkpoints/<session-id>"
```

Look for `status: "recovery_required"` and review the first item in
`pending_tools`. Replay must follow the returned `call_id` order.

## 2. Inspect before replaying

For `write_file`, `edit_file`, `run_command`, or `git`, inspect the current
workspace and diff first. The checkpoint means the call was durable before
execution, not that Docker definitely stopped before its side effect.

## 3. Explicitly replay one call

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -H "X-authentik-uid: <uid>" \
  -d '{"call_id":"<pending-call-id>","confirm":true}' \
  "<agent-runtime>/api/v1/dev/checkpoints/<session-id>/replay"
```

Repeat with `next_call_id` until the response reports
`status: "ready_to_resume"`. Only direct sandbox tools are replayable;
`Task`, MCP, web, and other meta-tools are rejected so they cannot be
reconstructed outside their original approval context.

## 4. Continue the model turn

Once all pending tools are replayed, continue the neutral history with an
empty-message DevHarness request:

```json
{
  "messages": [],
  "model": "default",
  "stream": true,
  "session_id": "<session-id>",
  "dev_mode": true,
  "dev_resume": true
}
```

Send a normal new user turn after this continuation finishes. A `dev_resume`
request uses the server checkpoint history and does not append a new prompt.
