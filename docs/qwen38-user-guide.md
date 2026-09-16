# Qwen 3.8 Local Heavy

Qwen 3.8 is available in Memex as an opt-in local profile. It assigns
`qwen3.8:27b` to all seven Team Builder roles: coordinator, architect, coder,
DevOps, researcher, analyst, and verifier.

Applying the preset only changes the Team Builder editor. Select **Save Config**
to persist it. Existing role settings remain unchanged if the preset is not
saved.

## Context profiles

Use Chat Settings to choose the request budget:

| Profile | Effective context | Use |
| --- | ---: | --- |
| Auto | Task-derived | Chat/vision uses Chat; Code/swarm uses Project |
| Chat | 32,768 tokens | Ordinary chat and image analysis |
| Project | 65,536 tokens | Code workspace and swarm project work |
| Long | 122,880 tokens | Explicit long repository or document analysis |

**Auto** is the default selection. It omits `context_profile` from the request
so the backend policy derives `chat` for ordinary chat and vision, or `project`
for Code and swarm work. You can explicitly choose Chat, Project, or Long when
you need to override that task default; Long is never selected implicitly. The
response metadata reports the server's effective token budget; that value is
authoritative when it differs from a model catalog maximum.

## Project safety and status

The active project appears beside the conversation. Projects backed by a Git
source are marked **LIVE REPO** so you can confirm the target before approving
changes.

Approval cards remain separate from model queue status. **Model Loading** means
the model is being loaded, **Model Busy** means it is resident and waiting for
the current inference slot, and an approval card means a tool action is waiting
for your decision. Existing Plan, session, and workspace permission behavior
remains in force.

The runtime emits a `model_metadata` event with `requested_model`,
`actual_model`, `provider`, `fallback`, `context_profile`, and
`effective_context_tokens`. The UI renders requested and actual model names
separately, marks a fallback explicitly, and uses the server-effective context
for the usage bar. These fields describe observed runtime metadata; the UI does
not infer them from a catalog entry or a mocked client value.
