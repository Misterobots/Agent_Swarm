# Friday Request Origin and Image Delivery

Document ID: CAP-FRIDAY-001  
Domain: Voice Assistant / Home Automation  
Owner: Platform  
Reviewers: Architecture, Operations, Security  
Status: Deployed  
Version: 1.2  
Last Updated: 2026-08-14  
Review Due: 2026-09-13  
Source of Truth: services/friday_brain/main.py; services/friday_brain/tools.py; execution_plane/docker-compose.yml  
Related Controls: MAESTRO L2, MAESTRO L4, MAESTRO L6  
Related Evidence: Live Justin-phone image notification and GPU-isolation test, 2026-08-14  
Supersedes: None

## Summary

Friday and Sable share the `friday_brain` service. This capability gives them a real image-generation and Home Assistant delivery path while establishing the first request-origin conventions used for device-local behavior.

Image delivery is asynchronous: Friday identifies the requested source, Art Studio generates an image or the Internet-image route finds one, and Home Assistant sends it to a Companion App device. Friday must not claim success until Home Assistant accepts the delivery calls. Completion and failure notifications go only to the selected delivery device; image delivery does not proactively announce through the Google Mini or another satellite.

## Current Status

| Scope | Status | Last verified | Notes |
|---|---|---:|---|
| Library satellite to associated speaker | Verified | 2026-08-12 | `friday-library` resolves to `media_player.google_mini_voice` |
| Image generation and push to Justin's phone | Verified | 2026-08-13 | Push arrived on the physical phone |
| Push tap opens image | Deployed | 2026-08-13 | Corrected after first push opened the HA dashboard; requires repeat verification |
| Persistent HA notification record | Deployed | 2026-08-13 | Corrected after first push left no HA notification history; requires repeat verification |
| Device-only image completion notification | Implemented | 2026-08-13 | Live workflow reached `sent`; physical phone receipt and Google Mini silence await user confirmation |
| Friday-safe image GPU route | Verified | 2026-08-14 | Friday image test loaded GPU 0 only; GPU 1 stayed at its Friday voice-stack allocation |
| Automatic originating-phone detection | Planned | — | HA request currently lacks reliable device metadata |
| Native user/device/area origin metadata | Planned | — | Requires an HA integration or proxy change |

## User Contract

### Supported

- “Send an image of a cat.” prompts for **Internet image** or **generated image**, then delivers to Justin's Phone by default.
- “Find an image of a cat.” uses Internet search and sends the result to Justin's Phone by default.
- “Generate an image of a cat.” uses the local generation workflow and sends the result to Justin's Phone by default.
- “Any luck with the image?” returns the tracked job state.
- Bare media commands from the configured library satellite act on its associated speaker.

### Explicitly unsupported

- “Send it to this phone” when the request does not carry a resolvable phone identity.
- Silent selection of a person's phone when no recipient was named, except for the opted-in `FRIDAY_DEFAULT_IMAGE_TARGET` (Justin's Phone).
- Claiming an image was sent merely because generation was requested.

### Success and failure language

- **Starting:** Friday may say generation has started and name the selected target.
- **Success:** Friday may say the image was sent only after generation succeeds and HA accepts both the persistent record and mobile push.
- **Failure:** Friday pushes the failure to the selected delivery device and stores the latest failure state for follow-up questions. She does not announce it through a speaker.
- **Ambiguous source:** Friday asks whether to find an Internet image or generate one. Only explicit source wording takes an automatic path; this is intentionally stricter than a 70% confidence threshold.
- **Recipient:** Friday defaults to `FRIDAY_DEFAULT_IMAGE_TARGET`; an explicit recipient always overrides it.

## Architecture and Data Flow

```text
Assist request
  -> friday_brain request-origin alias resolution
  -> deterministic image-intent gate
  -> agent_runtime /v1/art/generate/image
  -> poll /v1/art/jobs/{job_id}
  -> delivered_artifacts image URL
  -> HA persistent_notification.create
  -> HA notify.mobile_app_<device>
  -> Companion App image notification
```

The deterministic gate exists so model selection or reasoning behavior cannot invent a delivery action.

## Request Origin Model

Friday currently receives no reliable HA `device_id`, `user_id`, `area_id`, or mobile notification target. Fixed satellites are identified indirectly through a unique request model alias.

The target normalized structure is:

```json
{
  "source": "model_alias | ha_metadata | explicit_user_target",
  "device_id": null,
  "satellite_id": null,
  "user_id": null,
  "area_id": null,
  "speaker_entity_id": null,
  "notify_service": null,
  "trusted": false
}
```

Resolution precedence:

1. Trusted HA request metadata, once implemented.
2. Explicit target named in the current request.
3. Configured pipeline/model alias for fixed devices.
4. No target: clarify; never guess a person or device.

The current library mapping is:

```text
friday-library -> media_player.google_mini_voice
```

Justin's Phone is the opted-in default recipient for Friday image delivery. An explicit recipient in a request always overrides it.

## Source-of-Truth Files

| Path | Responsibility |
|---|---|
| `services/friday_brain/main.py` | Image intent, recipient resolution, job tracking, generation polling, user-facing state |
| `services/friday_brain/tools.py` | HA notification delivery and persistent notification record |
| `services/friday_brain/hass_resolver.py` | Existing HA entity and area resolution behavior |
| `execution_plane/docker-compose.yml` | Runtime URLs, target aliases, satellite-to-speaker configuration |
| `agents/main.py` | Art Studio generation and job-status API |
| `agents/specialized/image_gen.py` | Image generation and `delivered_artifacts` output contract |
| `agents/utils/gpu_queue.py` | GPU-zone transitions, including Friday-safe `image_fast` routing |

## Configuration Contract

| Variable | Required | Default | Purpose | Sensitive |
|---|---:|---|---|---:|
| `FRIDAY_NODE_SPEAKERS` | No | Empty | JSON model-alias to `media_player` mapping | No |
| `FRIDAY_IMAGE_RUNTIME_URL` | No | `http://agent-runtime:8000` | Internal Art Studio API | No |
| `FRIDAY_IMAGE_PUBLIC_BASE_URL` | No | `http://192.168.2.101:8008` | URL the phone uses to fetch generated images | No |
| `FRIDAY_IMAGE_TARGETS` | No | Justin phone test alias | JSON spoken alias to HA notify service | Potentially personal |
| `FRIDAY_DEFAULT_IMAGE_TARGET` | No | `justin phone` | Default alias for Friday image delivery | Potentially personal |
| `FRIDAY_IMAGE_MODEL` | No | `sdxl-turbo-preview` | Single-GPU ComfyUI image profile for Friday delivery | No |
| `FRIDAY_IMAGE_STEPS` | No | `4` | Friday image request step override | No |
| `FRIDAY_IMAGE_WIDTH` / `FRIDAY_IMAGE_HEIGHT` | No | `768` | Friday image request dimensions | No |
| `HOME_ASSISTANT_URL` | Yes | LAN HA URL | HA REST endpoint | No |
| `HOME_ASSISTANT_TOKEN` | Yes | None | Authorizes HA service calls | Yes |

Example target map:

```json
{
  "justin phone": "mobile_app_justin_s_phone",
  "fire tablet": "mobile_app_firetab"
}
```

Do not commit tokens or household-specific secrets.

## GPU Isolation Policy

GPU 1 is reserved for Friday's dedicated Qwen, STT, and TTS services. ComfyUI and OmniGen are pinned to GPU 0. Friday image delivery explicitly requests the `image_fast` queue context and the SDXL-Turbo profile; that path leaves ComfyUI available on GPU 0 and must not warm the dual-GPU Klein/FLUX service. After a local generation has been delivered, Friday calls ComfyUI's `/free` endpoint with `unload_models` and `free_memory`; the server remains available but its model weights do not stay resident.

Internet-image lookup uses Moondream on Turing's RTX 3070 Ti, not Lovelace. It describes the downloaded candidate and Friday derives a visible keyword-match percentage from that description. Moondream is requested with `keep_alive: 0`, so it releases Turing VRAM after each occasional check. A cold lookup added about 12 seconds in the 2026-08-14 verification; do not make it part of ordinary text/voice turns.

The heavyweight `image` / Klein route remains a separate Art Studio capability and may claim GPU 1 if explicitly invoked. Do not use it while Friday availability is required without scheduling or an explicit maintenance window.

## Failure and Degraded Behavior

| Condition | Observable behavior | Recovery or fallback |
|---|---|---|
| Recipient missing | Friday asks which device | Name a configured target |
| Art Studio unavailable | Job becomes failed; selected device receives a failure push | Restore `agent_runtime`, retry |
| Generation exceeds ten minutes | Job becomes failed with timeout | Inspect Art Studio/GPU queue |
| HA persistent record rejected | Delivery is reported failed | Check HA token and `persistent_notification` service |
| Mobile push rejected | Delivery is reported failed | Check notify service and Companion registration |
| Image URL unreachable from phone | Push may arrive without a usable image | Use a phone-reachable HTTPS artifact endpoint |
| Web candidate scores 50–79% | Friday holds it and states the score | Say “send it” or “generate one instead” |
| Web candidate scores below 50% | Friday states no close match and offers generation | Say “generate one instead” |
| Origin metadata absent | Device-local inference is unavailable | Explicit target or configured alias |

## Security and Privacy

- Recipient selection must come from trusted metadata, explicit speech, or a configured fixed-device alias.
- A client-supplied device ID must not become trusted merely because it appears in JSON; native origin metadata needs authentication at the HA integration boundary.
- HA tokens remain environment secrets.
- Image artifacts use an expiring HMAC-signed HTTPS URL through the Friday proxy; do not expose the underlying artifact directory or agent-runtime port publicly.
- Persistent notifications retain the image link in HA until dismissed.

## Deployment and Rollback

Deploy Friday-only changes locally on Lovelace:

```powershell
docker compose -f execution_plane/docker-compose.yml build friday-brain
docker compose -f execution_plane/docker-compose.yml up -d friday-brain
curl.exe -s http://127.0.0.1:8000/health
```

Rollback by reverting the relevant source/config change and rebuilding `friday-brain`. Clearing `FRIDAY_IMAGE_TARGETS` disables recipient resolution without disabling the rest of Friday.

## Verification

### End to end

1. Say “Send an image of a cat to Justin's phone.”
2. Confirm Friday reports only that generation started.
3. Ask “Any luck?” during generation and confirm she reports the real pending state.
4. Confirm the mobile push arrives with an image preview.
5. Tap the push and confirm the generated image opens, not the HA default dashboard.
6. Open HA Notifications and confirm a persistent Friday record contains an **Open image** link.
7. Issue “Send me an image of a cat” and confirm Friday asks for Internet versus generated, then defaults delivery to Justin's Phone.
8. Stop or block Art Studio and confirm Friday reports failure rather than success.
9. Confirm neither successful nor failed image delivery produces a Google Mini announcement.
10. During a Friday image request, confirm ComfyUI reports GPU 0 and GPU 1's Friday allocation remains stable.
11. Say “Find an image of …” and confirm a 50–79% result is not pushed until approval; confirm a lower score offers generation instead.
12. Confirm `ollama ps` on Turing is empty after the web-image check and that ComfyUI releases its model after local delivery.

The first 2026-08-13 test verified steps 1–4. A second test generated a watercolor orange cat, verified missing-recipient clarification, observed real `generating` then `sent` states, and confirmed the image workflow contains no `_ha_announce` call. Physical verification of steps 4–6 and 9 remains pending user confirmation.

## Extension Procedure

### Add a notification device

1. Identify its HA Companion notify service.
2. Add one or more unique spoken aliases to `FRIDAY_IMAGE_TARGETS`.
3. Recreate `friday-brain` so the environment is refreshed.
4. Test explicit delivery, tap behavior, persistent history, and ambiguous-recipient handling.
5. Update this document's status table and evidence.

### Add a fixed satellite

1. Give its HA conversation pipeline a unique Friday model alias.
2. Add the alias and associated `media_player` to `FRIDAY_NODE_SPEAKERS`.
3. Verify bare volume commands affect only the co-located speaker.
4. Record the mapping here or in a future device-association registry.

### Add native origin metadata

1. Define and version the request-origin schema.
2. Modify the HA conversation integration or trusted proxy to populate it.
3. Authenticate the metadata source.
4. Normalize it into one `RequestOrigin` object before intent handling.
5. Add registry lookups for device, user, area, speaker, and notify target.
6. Keep explicit-target and alias fallbacks.
7. Add spoofing, ambiguity, and cross-user tests.
8. Record the architectural decision in an ADR before treating metadata as an authorization signal.

## Open Decisions

- Whether to implement native origin metadata as an HA custom integration or a trusted proxy.
- Whether generated artifacts should use authenticated HTTPS rather than a LAN URL.
- Whether persistent HA records should expire automatically.
- Where the long-term device/user/area association registry should live.

## Change Log

| Date | Version | Change | Evidence |
|---|---:|---|---|
| 2026-08-14 | 1.3 | Added Turing GPU vision verification, score-based web-image fallback, and post-delivery ComfyUI model release | Non-notifying cat lookup returned 50%; Friday offered generation instead; Turing verifier unloaded; ComfyUI `/free` returned 200 |
| 2026-08-14 | 1.4 | Added opted-in Justin's Phone default and strict source disambiguation for generic image requests | Generic image wording asks Internet versus generated; explicit source wording routes automatically |
| 2026-08-14 | 1.2 | Pinned ComfyUI and OmniGen to GPU 0; added Friday-safe `image_fast` route and SDXL-Turbo delivery profile | Cat image generated and Friday reported phone delivery; GPU 1 allocation unchanged |
| 2026-08-13 | 1.1 | Restricted image completion and failure notifications to the selected delivery device; removed Google Mini announcements | Verification pending |
| 2026-08-13 | 1.0 | Added real image generation, explicit recipient resolution, mobile push, persistent HA record, and request-origin design | Live Justin-phone push received |

## Related Documents

- [Feature and Capability Documentation Standard](../governance/feature_documentation_standard.md)
- [Friday Life-Assistant Capability Map](../friday_life_assistant_needs.md)
- [Documentation Index](../INDEX.md)
