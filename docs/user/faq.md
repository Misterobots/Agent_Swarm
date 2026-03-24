# Frequently Asked Questions

> **Back to:** [Documentation Index](../INDEX.md)

---

## General Usage

**Q: Why is the AI taking a long time to respond?**

The Hive runs a Solver → Verifier → Corrector loop for coding tasks. A slow response usually means the Corrector was invoked to fix a first-pass response. This is normal and results in better output. You can watch the live progress in the "Chat" workspace — status messages appear as the loop progresses. If it takes more than 3 minutes, the stream may have stalled; reload the page and retry.

---

**Q: The AI said it can't do something. Why?**

Each agent has a **capability token** that limits which tools it can call. A coding agent cannot call IoT tools; a voice agent cannot write files to the workspace. This is by design — it prevents an AI from taking unintended actions outside its scope. If you need a capability that's being blocked, use the appropriate workspace (e.g., switch to "Maker Space" for IoT tasks).

---

**Q: Can I ask it to browse the internet?**

No. The Hive is fully air-gapped for inference. Models run locally and have no outbound internet access. This is intentional — it keeps your data private and prevents model "phone home" behaviors. Web-search tool integration is on the Phase 7 roadmap.

---

**Q: How do I generate an image?**

Switch to the **Media workspace**. Type a description of what you want. You can also adjust the model checkpoint, aspect ratio, and sampler settings in the sidebar before generating.

Alternatively, ask in the Chat workspace: "Generate an image of [description]" — the Router will detect the image intent and delegate to the Forge agent automatically.

---

**Q: Can I talk to BMO?**

Yes. Switch to the **Voice Studio workspace**. You can type or use your microphone. BMO responds using the RVC voice model. To adjust the voice or reference sample, use the sidebar controls in the Voice Studio.

---

**Q: How do I control my smart home?**

In the **Chat workspace**, just ask naturally: "Turn off the bedroom lights" or "What's the temperature in the living room?" The IoT agent translates these to Home Assistant API calls. It only executes changes explicitly listed in its approved tool set — it cannot make arbitrary API calls.

---

**Q: Can I see what the AI is "thinking"?**

Yes. In the Chat workspace, status messages appear in real-time showing which agent is running and what stage the MarsRL loop is at (`Solver generating...`, `Verifying...`, `Correcting...`).

For deeper inspection, open **Langfuse** at `http://192.168.2.102:3000` — every trace shows each agent step, the model inputs and outputs, and the quality score at each stage.

---

**Q: Where are my generated files?**

Files created by agents (code, images, exports) appear as **artifact cards** in the Chat workspace with a download button. Images and 3D models are also stored in the ComfyUI output folder and MinIO object storage. Check the **Control workspace** for a live file listing.

---

**Q: How do I access this outside my home?**

Use **Tailscale**. Connect to `dell-r730` (or its Tailscale IP) on port 80 as the gateway entry point. All services are available through that same gateway.

---

**Q: Is my data safe?**

Everything runs on your hardware. No data is sent to Anthropic, OpenAI, or any other cloud AI service. Traces are stored in Langfuse on your Control Node. The only outbound network calls are:
- Model downloads via Ollama (when you pull a new model)
- Tailscale VPN handshake (for remote access)

All AI interactions are logged locally to Langfuse and Loki. If you want to review or delete your traces, use the Langfuse dashboard.

---

## Errors & Issues

**Q: I see "System Offline" in the sidebar.**

The health check couldn't reach the agent runtime. Common causes:
1. The `agent-runtime` container on Justin-PC is not running
2. Network issue between R730 and Justin-PC
3. Justin-PC is powered off or sleeping

Check the **Control workspace** for node status, or ask an admin to check `docker compose ps` on Justin-PC.

---

**Q: The image generation failed with "No connection to ComfyUI".**

ComfyUI is GPU-bound and may have been evicted to free VRAM for a training run or another heavy model. Wait a few minutes and try again. If the training pipeline is running, ComfyUI will be unavailable until it finishes.

---

**Q: I asked for code and got an error about "max iterations reached".**

The Corrector ran out of attempts (default: 2 cycles). The problem was too complex for the model to fix automatically. Try rephrasing the request with more specific requirements, or break it into smaller steps. You can also switch to the **Coding workspace** for interactive debugging.

---

**Q: A voice response sounds wrong or choppy.**

The BMO voice uses RVC reconstruction. Issues can occur when the input text is very long or contains unusual characters. Try shorter, cleaner sentences. Also check that the `bmo-voice` and `voice-engine` containers are running on Justin-PC.

---

**Q: Grafana shows "No Data" on some panels.**

If you just deployed or restarted services, metrics take up to 15 seconds to appear (Prometheus scrape interval). For PostgreSQL panels (training, template scores), data only appears after the agent runtime has processed requests and populated the `swarm.*` tables. If problems persist, see [Admin: Troubleshooting](../admin/troubleshooting.md).

---

*For admin-level issues, see [Troubleshooting](../admin/troubleshooting.md) · [Back to Index](../INDEX.md)*
