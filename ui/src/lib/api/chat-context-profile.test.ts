import assert from "node:assert/strict";
import test from "node:test";
// Node's strip-types runner needs explicit extensions; the build uses the same modules normally.
// @ts-expect-error TS5097: runtime test imports TypeScript source directly.
import { requestContextProfile, resolveContextProfile } from "./chat-context-profile.ts";
// @ts-expect-error TS5097: runtime test imports TypeScript source directly.
import { mergeModelMetadata, resetTurnMetadata } from "./model-metadata-state.ts";

test("auto derives chat for ordinary chat and vision requests", () => {
  assert.equal(resolveContextProfile("auto", "chat", false), "chat");
  assert.equal(resolveContextProfile("auto", "chat", false), "chat");
  assert.equal(requestContextProfile("auto"), undefined);
});

test("auto derives project for Code and swarm requests", () => {
  assert.equal(resolveContextProfile("auto", "code", false), "project");
  assert.equal(resolveContextProfile("auto", "chat", true), "project");
});

test("explicit profiles are preserved and long is never implicit", () => {
  assert.equal(resolveContextProfile("chat", "code", false), "chat");
  assert.equal(resolveContextProfile("project", "chat", false), "project");
  assert.equal(resolveContextProfile("long", "code", true), "long");
  assert.equal(requestContextProfile("long"), "long");
});

test("a new run cannot inherit fallback or context metadata", () => {
  const first = mergeModelMetadata(null, {
    requestedModel: "qwen3.8:27b",
    actualModel: "qwen3:14b",
    provider: "ollama",
    fallback: true,
    contextProfile: "chat",
    effectiveContextTokens: 32768,
  }, "first", []);
  assert.equal(first.fallback, true);

  const second = mergeModelMetadata(resetTurnMetadata(), {
    requestedModel: "qwen3.8:27b",
    actualModel: "qwen3.8:27b",
    provider: "ollama",
    fallback: false,
    contextProfile: "project",
    effectiveContextTokens: 65536,
  }, "second", []);
  assert.equal(second.fallback, false);
  assert.equal(second.effectiveContextTokens, 65536);
  assert.equal(second.turnId, "second");
});
