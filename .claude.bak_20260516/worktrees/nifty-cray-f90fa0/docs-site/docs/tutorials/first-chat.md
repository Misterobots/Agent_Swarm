---
title: "Tutorial: Your First Chat"
---

# Your First Chat

Send your first message to Memex and understand how it processes your request.

## What You'll Learn

- How to access the chat interface
- How messages flow through the system
- How to interpret responses

## Step 1: Open the Chat Interface

Navigate to the Hive UI:

```
http://{{ turing_ip }}/
```

You'll see the chat interface with a text input at the bottom.

## Step 2: Send a Message

Type a simple question:

> What can you help me with?

Press **Enter** or click the send button.

## Step 3: Watch the Flow

Behind the scenes, your message flows through:

1. **Hive UI** — sends to Agent Runtime API
2. **Router** ({{ router_model }}) — classifies your intent as `CONVERSATION`
3. **Dispatcher** (`church.py`) — routes to the `CONVERSATION` handler
4. **Solver** ({{ solver_model }}) — generates a response
5. **MarsRL Verifier** ({{ verifier_model }}) — checks safety and quality
6. **Response** streams back to the UI

You should see a streaming response appear in real-time.

## Step 4: Try Different Intents

Each of these triggers a different agent:

| Message | Intent | Agent |
|---------|--------|-------|
| "What's 2+2?" | `CONVERSATION` | Solver |
| "Draw a sunset" | `IMAGE` | Image Agent |
| "Turn on the lights" | `IOT_CONTROL` | IoT Agent |
| "Generate a 3D model of a chair" | `3D` | 3D Pipeline |
| "Write a short story about a spaceship" | `CREATIVE` | Creative Writer |

## Step 5: Check the Trace

Open Langfuse at `http://{{ hopper_ip }}:3000` to see the full trace of your conversation, including:

- Intent classification scores
- Model latency
- Token usage
- Verifier results

## Next Steps

- [Generate an Image](generate-image.md) — try creative generation
- [User Guide: Chat](../user-guide/chat.md) — full chat feature reference

