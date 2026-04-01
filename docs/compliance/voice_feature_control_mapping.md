# Voice Feature Control Mapping

Document ID: COMP-VOICE-001
Domain: Compliance
Owner: Compliance
Reviewers: Security, Platform, Product
Status: Approved
Version: 1.0
Last Updated: 2026-03-31
Review Due: 2026-04-30
Source of Truth: agents/specialized/voice_assistant.py, agents/main.py
Related Controls: MAESTRO L2, L3, L4, L6, L7
Related Evidence: docs/compliance/eval_identity_security.md, docs/specs/langfuse_observability_spec.md
Supersedes: None

## Purpose
Map voice-facing capabilities to implementation, runtime surfaces, controls, and evidence paths.

## Voice Feature Inventory
1. Voice chat ingress endpoint.
2. Persona-aware conversational response generation.
3. Smart-home action invocation from voice intent.
4. Weather/time/news tool-assisted factual responses.
5. Pre-recorded sample fast-path response selection.
6. Dynamic cloned-voice audio synthesis path.
7. Voice response metadata path (`audio_path`) back to caller.

## Mapping Matrix
| Voice Feature | Primary Implementation | Runtime Surface | Control Domains | Evidence |
|---|---|---|---|---|
| Voice chat API ingress | agents/main.py (`POST /v1/voice/chat`) | Agent runtime API | L3, L4, L7 | docs/admin/security.md |
| Voice assistant orchestration | agents/specialized/voice_assistant.py (`VoiceAssistantAgent.process`) | Ollama + agent runtime | L4, L6 | docs/admin/design_framework.md |
| Smart-home tool calls from voice | SmartHomeTool wrapper (`turn_on_device`, `turn_off_device`, `get_device_state`) | Home Assistant API | L3, L4, L7 | docs/compliance/eval_identity_security.md |
| External factual tool calls | WeatherTool, TimeTool, NewsTool | Tooling layer via phi Agent | L4, L6 | docs/specs/langfuse_observability_spec.md |
| Sample phrase deterministic path | voice_samples_map (`get_sample_path`, `find_sample_in_response`) | Local voice sample store | L2, L6 | docs/user/overview.md |
| Voice cloning synthesis | specialized/voice_cloning.py via `clone_voice` | Local audio generation pipeline | L4, L6 | docs/admin/technical_reference.md |
| Response metadata return contract | Message metadata (`audio_path`) | API payload contract | L2, L6 | docs/user/framework.md |

## Control Coverage Notes
1. Authentication and authorization are endpoint-level concerns and should align with API auth contract for protected classes.
2. Tool invocation safety relies on guardrails in voice assistant instructions and downstream tool-level controls.
3. Observability coverage depends on runtime logging and trace instrumentation quality.

## Contextual Error Log
- No runtime execution errors during inventory extraction; mapping generated from static code inspection.

## Next Verification Actions
1. Add endpoint auth tests for `/v1/voice/chat` under endpoint-class policy.
2. Add tool-call audit assertions (who invoked which smart-home action).
3. Validate no sensitive audio metadata leakage in response payloads.

## References
- docs/compliance/feature_control_traceability_matrix.md
- docs/security/api_authentication_contract.md
- docs/admin/security.md
