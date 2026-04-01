# IoT Feature Control Mapping

Document ID: COMP-IOT-001
Domain: Compliance
Owner: Compliance
Reviewers: Security, Platform, Product
Status: Approved
Version: 1.0
Last Updated: 2026-03-31
Review Due: 2026-04-30
Source of Truth: agents/specialized/iot_agent.py, agents/tools/iot_ops.py, docs/specs/wokwi_integration_spec.md
Related Controls: MAESTRO L3, L4, L6, L7
Related Evidence: docs/specs/wokwi_integration_spec.md, docs/compliance/eval_identity_security.md
Supersedes: None

## Purpose
Map IoT and home-automation features to implementation modules, runtime surfaces, control domains, and evidence.

## IoT Feature Inventory
1. Home Assistant state discovery.
2. Home Assistant service execution (device control).
3. MQTT publish/subscribe operations.
4. ESPHome compile/upload workflow.
5. Wokwi simulation project creation.
6. Wokwi part placement and wiring operations.
7. Safety guardrails for lock/alarm and firmware deployment flow.

## Mapping Matrix
| IoT Feature | Primary Implementation | Runtime Surface | Control Domains | Evidence |
|---|---|---|---|---|
| Entity state retrieval | agents/tools/iot_ops.py (`get_states`) | Home Assistant REST | L3, L6 | docs/admin/technical_reference.md |
| Device service control | agents/tools/iot_ops.py (`call_service`) | Home Assistant REST | L3, L4, L7 | docs/compliance/eval_identity_security.md |
| IoT orchestration agent | agents/specialized/iot_agent.py (`get_iot_agent`) | Ollama + tool chain | L4, L6 | docs/admin/design_framework.md |
| MQTT operations | tools/mqtt_ops.py (referenced by iot_agent) | MQTT broker path | L3, L6, L7 | docs/specs/wokwi_integration_spec.md |
| ESPHome compile/upload | tools/esphome_ops.py (referenced by iot_agent) | Build/deploy pipeline | L4, L6, L7 | docs/specs/wokwi_integration_spec.md |
| Wokwi simulation bootstrapping | tools/wokwi_ops.py (`create_simulation`) | Local simulation workspace | L4, L6 | docs/specs/wokwi_integration_spec.md |
| Wokwi hardware composition | tools/wokwi_ops.py (`add_part`, `connect_wires`) | Local simulation workspace | L4, L6 | docs/specs/wokwi_integration_spec.md |

## Security and Safety Notes
1. `iot_ops.py` supports mock mode (`IOT_MOCK_MODE=true`) to reduce blast radius during testing.
2. `iot_ops.py` now enforces confirmation for sensitive lock/alarm actions before service execution, and iot_agent instructions mirror that guardrail at the planning layer.
3. `iot_ops.py` emits structured audit logs for sensitive action attempts, confirmation state, and execution outcome (`[IoT-AUDIT]`).
4. Sensitive-action counters are exported via Prometheus metrics (`iot_sensitive_actions_total`, `iot_sensitive_actions_blocked_total`) and consumed by runtime alert rules.
5. Endpoint/token enforcement must align with API authentication contract for production hardening.

## Contextual Error Log
- No runtime execution errors during inventory extraction; mapping generated from static code and spec review.
- 2026-03-31 verification converted the prior lock/alarm confirmation gap into enforced service-layer behavior validated by `tests/test_iot_controls.py`.
- 2026-03-31 follow-up hardening added auditable sensitive-action telemetry in service-layer execution logs.
- 2026-03-31 monitoring hardening added alertable IoT-sensitive action metrics and validated Prometheus rule syntax (`6 rules found`).

## Next Verification Actions
1. Add explicit auth coverage tests for any exposed IoT control endpoints.
2. Extend confirmation enforcement to additional sensitive domains if new actuator classes are introduced.
3. Add centralized dashboard panels and retained alert evidence for `[IoT-AUDIT]` and sensitive-action counters across MQTT and Home Assistant service-call paths.

## References
- docs/compliance/feature_control_traceability_matrix.md
- docs/security/api_authentication_contract.md
- docs/specs/wokwi_integration_spec.md
