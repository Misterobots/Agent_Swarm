# Friday Assist UI continuation

## Purpose

`friday_continuation` is a Home Assistant custom conversation entity that wraps the active Friday agent, currently `conversation.friday_library`. It preserves the existing Ollama/Friday request path, Home Assistant tools, and the agent's own chat history.

The wrapper changes only `ConversationResult.continue_conversation` for the Assist UI. Friday keeps the conversation open when her completed reply is a clear follow-up question, including direct questions and common selection prompts. It closes after status updates, commands, and ordinary answers.

## Installation and configuration

1. Copy `home_assistant/custom_components/friday_continuation` into Home Assistant's `/config/custom_components/`.
2. Restart Home Assistant.
3. In **Settings → Devices & services → Add integration**, add **Friday Assist Continuation** and select `conversation.friday_library`.
4. In the **Friday** Assist pipeline, change the conversation agent to `conversation.friday_continuation`.

## Scope and safeguards

- This is deliberately Assist-UI focused; it does not keep Google Mini satellites listening and does not change wake-word or TTS behavior.
- The underlying Friday entity remains the source of model responses, tool calls, recipient routing, image delivery, and conversation history.
- Continuation is based on Friday's final speech only. An empty or informational response never opens the mic.

## Verification

In Assist UI, ask Friday a request that needs a choice, such as “send an image to my phone.” When she asks who should receive it, the input should remain active for the reply. Then try “what is the weather?”; after the answer, the conversation should close normally.
