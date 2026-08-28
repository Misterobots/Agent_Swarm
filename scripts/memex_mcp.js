#!/usr/bin/env node
"use strict";

// Codex-facing stdio MCP adapter for the local Agent_Swarm chat API.
// Keep this repository-owned: ~/.codex/config.toml points here.
const readline = require("node:readline");

const API_URL = process.env.MEMEX_API_URL || "http://127.0.0.1:8008/v1/chat/completions";
const MODEL = process.env.MEMEX_MODEL || "qwen3.6:27b";

const tools = [
  ["memex_swarm", "Multi-agent build coordinator", { prompt: { type: "string" }, answer: { type: "string" } }, ["prompt"]],
  ["memex_perspectives", "Multi-lens research with divergent and convergent synthesis", { query: { type: "string" } }, ["query"]],
  ["memex_research", "Deep research with web grounding", { query: { type: "string" } }, ["query"]],
  ["memex_think", "Extended reasoning", { problem: { type: "string" } }, ["problem"]],
  ["memex_design", "HTML UI mockup generation", { prompt: { type: "string" } }, ["prompt"]],
  ["memex_plan", "Structured plan without execution", { task: { type: "string" } }, ["task"]],
  ["memex_workshop", "Product discovery and brief generation", { idea: { type: "string" } }, ["idea"]],
  ["memex_recall", "Search persistent memory", { query: { type: "string" } }, ["query"]],
  ["memex_remember", "Store persistent memory", { content: { type: "string" } }, ["content"]],
  ["memex_chat", "Full Memex pipeline with memory and grounding", { message: { type: "string" } }, ["message"]],
].map(([name, description, properties, required]) => ({
  name,
  description,
  inputSchema: { type: "object", properties, required, additionalProperties: false },
}));

function requestFor(name, args) {
  const value = args.prompt || args.query || args.problem || args.task || args.idea || args.content || args.message || "";
  const modes = {};
  let message = value;
  if (name === "memex_swarm") {
    message = `/swarm ${value}${args.answer ? `\n\nUser clarification: ${args.answer}` : ""}`;
    modes.swarm_mode = true;
  } else if (name === "memex_perspectives") {
    message = `/research Analyze from multiple independent perspectives, reconcile disagreements, and synthesize: ${value}`;
    modes.research_mode = true;
    modes.swarm_mode = true;
    modes.grounding_web = true;
  } else if (name === "memex_research") {
    message = `/research ${value}`;
    modes.research_mode = true;
    modes.grounding_web = true;
  } else if (name === "memex_think") {
    message = `/think ${value}`;
    modes.ultrathink_mode = true;
  } else if (name === "memex_design") {
    message = `/design ${value}`;
    modes.design_mode = true;
  } else if (name === "memex_plan") {
    message = `/plan ${value}`;
    modes.ultraplan_mode = true;
    modes.swarm_mode = true;
  } else if (name === "memex_workshop") {
    message = `/workshop ${value}`;
    modes.workshop_mode = true;
  } else if (name === "memex_recall") {
    message = `Recall relevant persistent memories for: ${value}`;
  } else if (name === "memex_remember") {
    message = `Remember this exactly: ${value}`;
  }
  return { model: MODEL, messages: [{ role: "user", content: message }], stream: true, ...modes };
}

async function callMemex(name, args) {
  const response = await fetch(API_URL, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(requestFor(name, args)),
    signal: AbortSignal.timeout(Number(process.env.MEMEX_TIMEOUT_MS || 900000)),
  });
  if (!response.ok) throw new Error(`Memex HTTP ${response.status}: ${await response.text()}`);
  let output = "";
  for (const line of (await response.text()).split(/\r?\n/)) {
    if (!line.startsWith("data:")) continue;
    const data = line.slice(5).trim();
    if (!data || data === "[DONE]") continue;
    try {
      const parsed = JSON.parse(data);
      const delta = parsed.choices?.[0]?.delta;
      if (typeof delta?.content === "string") output += delta.content;
      else if (delta?.type === "error" && delta?.content) output += `\n[MEMEX ERROR] ${delta.content}`;
    } catch { /* ignore keepalives/non-JSON data */ }
  }
  return output.trim() || "[MEMEX ERROR] The runtime returned no response content.";
}

async function dispatch(message) {
  const { id, method, params = {} } = message;
  if (method === "initialize") return { jsonrpc: "2.0", id, result: { protocolVersion: "2025-06-18", capabilities: { tools: {} }, serverInfo: { name: "memex", version: "1.0.0" } } };
  if (method === "notifications/initialized") return null;
  if (method === "ping") return { jsonrpc: "2.0", id, result: {} };
  if (method === "tools/list") return { jsonrpc: "2.0", id, result: { tools } };
  if (method === "tools/call") {
    const tool = tools.find((item) => item.name === params.name);
    if (!tool) throw new Error(`Unknown tool: ${params.name}`);
    const text = await callMemex(params.name, params.arguments || {});
    return { jsonrpc: "2.0", id, result: { content: [{ type: "text", text }], isError: text.startsWith("[MEMEX ERROR]") } };
  }
  return { jsonrpc: "2.0", id, error: { code: -32601, message: `Method not found: ${method}` } };
}

const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
rl.on("line", async (line) => {
  if (!line.trim()) return;
  let message;
  try { message = JSON.parse(line); } catch { return; }
  try {
    const response = await dispatch(message);
    if (response) process.stdout.write(`${JSON.stringify(response)}\n`);
  } catch (error) {
    process.stdout.write(`${JSON.stringify({ jsonrpc: "2.0", id: message.id, error: { code: -32603, message: String(error.message || error) } })}\n`);
  }
});
