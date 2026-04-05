#!/usr/bin/env python3
"""
Patch use-chat-stream.ts:
1. Add pipelineSteps state array
2. Intercept status/pipeline lines from content — divert to pipelineSteps, don't append to message
3. Expose pipelineSteps in the return value
"""

PATH = "/home/misterobots/Home_AI_Lab/ui/src/lib/hooks/use-chat-stream.ts"

with open(PATH) as f:
    content = f.read()

# ---------- 1. Add pipelineSteps state after latestThought ----------
old_states = '''  const [latestThought, setLatestThought] = useState<string | null>(null);
  const [streamMode, setStreamMode] = useState<StreamMode | null>(null);'''

new_states = '''  const [latestThought, setLatestThought] = useState<string | null>(null);
  const [pipelineSteps, setPipelineSteps] = useState<string[]>([]);
  const [streamMode, setStreamMode] = useState<StreamMode | null>(null);'''

if old_states in content:
    content = content.replace(old_states, new_states)
    print("[1] Added pipelineSteps state")
else:
    print("[1] ERROR: Could not find state block")

# ---------- 2. Reset pipelineSteps at stream start ----------
old_reset = '''      setStreamMode(null);
      thoughtTraceRef.current = [];'''

new_reset = '''      setStreamMode(null);
      setPipelineSteps([]);
      thoughtTraceRef.current = [];'''

if old_reset in content:
    content = content.replace(old_reset, new_reset)
    print("[2] Added pipelineSteps reset")
else:
    print("[2] ERROR: Could not find reset block")

# ---------- 3. Replace the content handler — intercept pipeline lines ----------
old_handler = '''          } else {
            const chunk = event.content || "";
            // Detect agent status lines (emoji prefix + Agent/Router/Cortex pattern)
            const statusMatch = chunk.match(/^[\\s\\n]*[\\p{Emoji_Presentation}\\p{Emoji}\\uFE0F]+\\s+.+?(?:Agent|Router|Cortex|JWT|Security|Analysis).*$/mu);
            if (statusMatch) {
              setStatusMessage(statusMatch[0].trim());
              setLatestThought(statusMatch[0].trim());
            }
            appendToMessage(convId!, assistantId, chunk);
          }'''

new_handler = '''          } else {
            const chunk = event.content || "";
            // Split chunk into lines to separate pipeline status from real content
            const lines = chunk.split("\\n");
            const contentParts: string[] = [];
            for (const line of lines) {
              const trimmed = line.trim();
              // Match pipeline/reasoning lines: emoji-prefixed agent status, bracketed tags, or system lines
              const isPipeline = /^[\\p{Emoji_Presentation}\\p{Emoji}\\uFE0F]+\\s+.+?(?:Agent|Router|Cortex|JWT|Security|Analysis|Ambiguous|Token|Input Cleared)/u.test(trimmed)
                || /^\\[.+?\\]/.test(trimmed);
              if (isPipeline && trimmed.length > 0) {
                // Divert to pipeline steps — don't put in message
                setPipelineSteps((prev) => [...prev, trimmed]);
                setStatusMessage(trimmed);
                setLatestThought(trimmed);
              } else {
                contentParts.push(line);
              }
            }
            // Only append non-pipeline content to the message
            const cleanContent = contentParts.join("\\n");
            if (cleanContent.length > 0) {
              appendToMessage(convId!, assistantId, cleanContent);
            }
          }'''

if old_handler in content:
    content = content.replace(old_handler, new_handler)
    print("[3] Replaced content handler with pipeline interceptor")
else:
    print("[3] ERROR: Could not find content handler")
    # Try to find what's there
    idx = content.find("appendToMessage(convId!, assistantId, chunk)")
    if idx > 0:
        snippet = content[max(0,idx-200):idx+200]
        print(f"  Found appendToMessage near: ...{snippet[-100:]}...")

# ---------- 4. Clear pipelineSteps in finally block ----------
old_finally = '''        setIsStreaming(false);
        setStatusMessage(null);
        setLatestThought(null);
        setStreamMode(null);'''

new_finally = '''        setIsStreaming(false);
        setStatusMessage(null);
        setLatestThought(null);
        setStreamMode(null);
        // Keep pipelineSteps visible briefly after stream ends (cleared on next send)'''

if old_finally in content:
    content = content.replace(old_finally, new_finally)
    print("[4] Patched finally block — pipelineSteps persist after stream")
else:
    print("[4] ERROR: Could not find finally block")

# ---------- 5. Add pipelineSteps to return value ----------
old_return = '''    tokenUsage,
    sendMessage,
    compactConversation,
    stopGeneration,'''

new_return = '''    pipelineSteps,
    tokenUsage,
    sendMessage,
    compactConversation,
    stopGeneration,'''

if old_return in content:
    content = content.replace(old_return, new_return)
    print("[5] Added pipelineSteps to return value")
else:
    print("[5] ERROR: Could not find return block")

with open(PATH, "w") as f:
    f.write(content)

print("\\nDone — use-chat-stream.ts patched")
