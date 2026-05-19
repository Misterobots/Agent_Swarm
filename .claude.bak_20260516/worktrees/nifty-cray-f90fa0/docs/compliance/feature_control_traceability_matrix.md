# Feature Control Traceability Matrix

Document ID: COMP-TRACE-001
Domain: Compliance
Owner: Compliance
Reviewers: Product, Security, Architecture
Status: Approved
Version: 1.0
Last Updated: 2026-03-31
Review Due: 2026-04-30
Source of Truth: docs/INDEX.md
Related Controls: MAESTRO L1-L7
Related Evidence: docs/evidence/
Supersedes: None

## Purpose
Map each user-facing feature to implementation modules, runtime services, controls, and evidence artifacts.

## Matrix
| Feature | Primary Implementation | Runtime Service | Control Domains | Evidence |
|---|---|---|---|---|
| Chat and orchestration | agents/main.py, agents/router.py | agent-runtime | L4, L6, L7 | docs/compliance/eval_agent_logic.md |
| Code quality loop (MarsRL) | agents/mars_loop.py, verifier/corrector modules | agent-runtime | L4, L6 | docs/evidence/maestro_full_audit_2026_02_22.md |
| Capability-gated tool use | agents/security/token_issuer.py, capability_gate.py | agent-runtime | L7, L6 | docs/evidence/phase5_jwt_ace_audit_2026_03_17.md |
| Workload identity | agents/security/spiffe_auth.py | spire-server, spire-agent | L7 | docs/compliance/eval_identity_security.md |
| Training pipeline | agents/training/* | training-runtime | L1, L2, L4, L6 | docs/evidence/phase6_training_pipeline_audit_2026_03_21.md |
| Image and 3D generation | agents/specialized/image_gen.py, forge agent | comfyui_gpu | L4, L6 | docs/user/art_studio_guide.md |
| Voice chat ingress | agents/main.py (`/v1/voice/chat`) | agent-runtime | L3, L4, L7 | docs/compliance/voice_feature_control_mapping.md |
| Voice assistant orchestration | agents/specialized/voice_assistant.py | agent-runtime, ollama | L4, L6 | docs/compliance/voice_feature_control_mapping.md |
| Voice smart-home control | SmartHomeTool in voice_assistant.py | Home Assistant API | L3, L4, L7 | docs/compliance/voice_feature_control_mapping.md |
| Voice sample and synthesis pipeline | voice_samples_map.py, voice_cloning.py | local voice pipeline | L2, L4, L6 | docs/compliance/voice_feature_control_mapping.md |
| IoT orchestration and guardrails | agents/specialized/iot_agent.py | agent-runtime | L4, L6, L7 | docs/compliance/iot_feature_control_mapping.md |
| IoT Home Assistant control | agents/tools/iot_ops.py | Home Assistant API | L3, L4, L7 | docs/compliance/iot_feature_control_mapping.md |
| IoT simulation and firmware workflow | tools/wokwi_ops.py, tools/esphome_ops.py | local simulation and build flow | L4, L6, L7 | docs/compliance/iot_feature_control_mapping.md |
| Observability and traces | Langfuse integration in router and loop | langfuse, clickhouse | L4, L6 | docs/specs/langfuse_observability_spec.md |

## Coverage Notes
1. This matrix is v1 and focuses on high-impact product features.
2. Remaining low-impact features are tracked in the documentation gap register.
