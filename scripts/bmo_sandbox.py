#!/usr/bin/env python3
"""
BMO Test Sandbox — test the full BMO experience without Raspberry Pi hardware.

Tests the complete pipeline:
  1. Input sample matching (instant pre-recorded clips)
  2. LLM response generation (via Ollama)
  3. Response sample scanning (embedded phrase detection)
  4. Emotion detection + face/pitch mapping
  5. TTS voice generation (optional, requires bmo-voice container)

Usage:
  # Interactive chat mode (LLM only, no TTS)
  python scripts/bmo_sandbox.py

  # Interactive chat with TTS audio generation
  python scripts/bmo_sandbox.py --tts

  # Single prompt test
  python scripts/bmo_sandbox.py --prompt "Hey BMO, turn on the lights"

  # Batch test a file of prompts (one per line)
  python scripts/bmo_sandbox.py --batch tests/bmo_test_prompts.txt

  # Custom Ollama host/model
  python scripts/bmo_sandbox.py --host 192.168.2.101 --port 11434 --model qwen3:14b
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime

# ---------------------------------------------------------------------------
# Inline copies of the sample map + emotion detector so the sandbox runs
# without Docker container imports (phi, HomeAssistant, etc.)
# ---------------------------------------------------------------------------

# We import the real modules where possible, fall back to inline stubs
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))
    from specialized.voice_samples_map import VOICE_SAMPLES_MAP, get_sample_path, find_sample_in_response
    from specialized.bmo_persona import BMO_SYSTEM_PROMPT, EMOTION_TRIGGERS
    IMPORTS_OK = True
except ImportError:
    IMPORTS_OK = False
    # Minimal fallback if running outside the project structure
    VOICE_SAMPLES_MAP = {}
    BMO_SYSTEM_PROMPT = "You are BMO from Adventure Time."
    EMOTION_TRIGGERS = {}

    def get_sample_path(text):
        normalized = re.sub(r'[^a-z0-9\s]', '', text.lower()).strip()
        return VOICE_SAMPLES_MAP.get(normalized)

    def find_sample_in_response(text):
        return None


def detect_emotion(text):
    """Mirror of bmo_driver.py detect_emotion() for sandbox testing."""
    t = text.lower()

    if "!" in t or any(w in t for w in ["excited", "yay", "awesome", "great", "love", "happy"]):
        if "!" in t:
            return "excited", 6, 1.3
        return "happy", 3, 1.15

    if any(w in t for w in ["sad", "sorry", "unfortunately", "bad news", "miss", "oh no"]):
        return "sad", -5, 0.7

    if any(w in t for w in ["whoa", "wow", "oh my", "gasp", "no way"]):
        return "surprised", 5, 1.2

    if any(w in t for w in ["yawn", "sleep", "bedtime", "nap", "dream", "sleepy"]):
        return "sleeping", -6, 0.6

    if "?" in t or any(w in t for w in ["hmm", "wonder", "think", "what if", "wait"]):
        return "thinking", 0, 0.9

    if any(w in t for w in ["error", "confused", "weird", "broken", "fail"]):
        return "error", -2, 0.85

    return "neutral", 0, 1.0


# ---------------------------------------------------------------------------
# Ollama LLM caller (no phi dependency needed)
# ---------------------------------------------------------------------------

def call_ollama(prompt, model, host, port, system_prompt):
    """Call Ollama, preferring /api/chat and falling back to /api/generate."""
    import requests

    chat_url = f"http://{host}:{port}/api/chat"
    chat_payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {"num_predict": 256},
    }

    t0 = time.time()
    try:
        resp = requests.post(chat_url, json=chat_payload, timeout=30)
        if resp.status_code == 404:
            raise requests.HTTPError("/api/chat unavailable", response=resp)
        resp.raise_for_status()

        elapsed = time.time() - t0
        data = resp.json()
        content = data.get("message", {}).get("content", "")

        # Strip thinking tags if model uses them (qwen3)
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        return content, elapsed, None
    except Exception as chat_err:
        # Compatibility fallback for Ollama variants that only expose /api/generate.
        gen_url = f"http://{host}:{port}/api/generate"
        gen_prompt = f"{system_prompt}\n\n{prompt}"
        gen_payload = {
            "model": model,
            "prompt": gen_prompt,
            "stream": False,
            "options": {"num_predict": 256},
        }
        try:
            resp = requests.post(gen_url, json=gen_payload, timeout=45)
            resp.raise_for_status()

            elapsed = time.time() - t0
            data = resp.json()
            content = data.get("response", "")
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            return content, elapsed, None
        except Exception as gen_err:
            err = (
                f"Ollama request failed (host={host}:{port}, model={model}). "
                f"chat_err={chat_err}; generate_err={gen_err}"
            )
            return None, 0, err


def call_tts(text, host, port=8100, pitch=3):
    """Call bmo-voice /speak endpoint for TTS + RVC."""
    import requests

    # Phonetic fix
    text = text.replace("BMO", "Beemo").replace("bmo", "beemo").replace("Bmo", "Beemo")

    url = f"http://{host}:{port}/speak"
    params = {"text": text, "pitch": pitch, "speed": 1.0, "method": "rmvpe"}

    t0 = time.time()
    try:
        resp = requests.post(url, params=params, timeout=30)
        if resp.status_code == 200:
            out_path = os.path.join("delivered_artifacts", f"bmo_sandbox_{int(time.time())}.wav")
            os.makedirs("delivered_artifacts", exist_ok=True)
            with open(out_path, "wb") as f:
                f.write(resp.content)
            return out_path, time.time() - t0, None
        return None, time.time() - t0, f"HTTP {resp.status_code}: {resp.text[:100]}"
    except Exception as e:
        return None, time.time() - t0, str(e)


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

FACE_MAP = {
    "excited":  "  ^_^  ",
    "happy":    "  ^.^  ",
    "sad":      "  ;_;  ",
    "surprised":"  O.O  ",
    "sleeping": "  -.-  ",
    "thinking": "  o.?  ",
    "error":    "  x_x  ",
    "neutral":  "  o.o  ",
}

def display_result(user_input, response, emotion, pitch, speed, sample_match,
                   response_sample, llm_time, tts_path, tts_time):
    """Pretty-print a single BMO interaction result."""
    face = FACE_MAP.get(emotion, "  o.o  ")

    print()
    print("=" * 70)
    print(f"  YOU:  {user_input}")
    print("-" * 70)

    if sample_match:
        print(f"  [SAMPLE FAST-PATH] -> {sample_match}")
        print(f"  BMO:  (pre-recorded clip)")
    else:
        print(f"  BMO:  {response}")
        print(f"  LLM:  {llm_time:.2f}s")

    print("-" * 70)
    print(f"  Face:    {face}  ({emotion})")
    print(f"  Pitch:   {pitch:+d} semitones")
    print(f"  Speed:   {speed:.2f}x")

    if response_sample:
        print(f"  Audio:   [RESPONSE SAMPLE] {response_sample}")
    elif tts_path:
        print(f"  Audio:   {tts_path} ({tts_time:.2f}s)")
    elif tts_time and not tts_path:
        print(f"  Audio:   [TTS FAILED]")
    else:
        print(f"  Audio:   [skipped — use --tts to enable]")

    # Quality checks
    issues = []
    if response:
        if any(c in response for c in ["*", "#", "```"]):
            issues.append("MARKDOWN DETECTED in response")
        if re.search(r'[\U00010000-\U0010ffff]', response):
            issues.append("EMOJI DETECTED in response")
        if re.search(r'\bI\b.*\b(will|am|can|have)\b', response) and "Beemo" not in response:
            issues.append("First-person detected (should use third-person 'Beemo')")
        if re.search(r'(?i)\bAs an AI\b|\blanguage model\b', response):
            issues.append("CHARACTER BREAK: AI self-reference")
        if re.search(r'\d{2,}', response):
            issues.append("Numeric digits found (should spell out numbers)")
        if "BMO" in response:
            issues.append("'BMO' found (should be 'Beemo' for TTS)")
        if len(response) > 300:
            issues.append(f"Response too long ({len(response)} chars) for voice")

    if issues:
        print(f"  {'='*50}")
        for issue in issues:
            print(f"  WARNING: {issue}")

    print("=" * 70)


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_single(user_input, model, host, port, tts_enabled, tts_host, tts_port):
    """Run one prompt through the full BMO pipeline."""

    # 1. Sample fast-path (input matching)
    sample_match = get_sample_path(user_input)
    if sample_match:
        emotion, pitch, speed = detect_emotion(user_input)
        display_result(user_input, None, emotion, pitch, speed, sample_match,
                       None, 0, None, 0)
        return

    # 2. Build context (time injection)
    now = datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        hint = "It is morning."
    elif 12 <= hour < 17:
        hint = "It is afternoon."
    elif 17 <= hour < 21:
        hint = "It is evening."
    else:
        hint = "It is nighttime."
    time_str = now.strftime("%A, %B %d at %I:%M %p")
    context = f"[System Context: Current time: {time_str}. {hint}]\nUser: {user_input}"

    # 3. LLM call
    response, llm_time, llm_err = call_ollama(context, model, host, port, BMO_SYSTEM_PROMPT)
    if llm_err:
        print(f"\n  LLM ERROR: {llm_err}")
        return

    # 4. Response sample scan
    response_sample = find_sample_in_response(response) if response else None

    # 5. Emotion detection
    emotion, pitch, speed = detect_emotion(response)

    # 6. TTS (optional)
    tts_path, tts_time = None, 0
    if tts_enabled and response and not response_sample:
        tts_path, tts_time, tts_err = call_tts(response, tts_host, tts_port, pitch)
        if tts_err:
            tts_time = tts_time  # keep timing even on failure

    # 7. Display
    display_result(user_input, response, emotion, pitch, speed, sample_match,
                   response_sample, llm_time, tts_path, tts_time)


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def run_preflight(args):
    """Check all required services and print a summary table. Returns True if all critical checks pass."""
    import requests

    tts_host = args.tts_host or args.host
    checks = []

    # 1. Ollama reachability
    ollama_url = f"http://{args.host}:{args.port}/api/tags"
    try:
        r = requests.get(ollama_url, timeout=6)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        model_ok = any(args.model.split(":")[0] in m for m in models)
        checks.append(("Ollama API",       True,  f"http://{args.host}:{args.port}"))
        checks.append((f"Model {args.model}", model_ok,
                        "available" if model_ok else f"NOT FOUND — available: {', '.join(models) or 'none'}"))
    except Exception as e:
        checks.append(("Ollama API",       False, str(e)))
        checks.append((f"Model {args.model}", False, "skipped (Ollama unreachable)"))

    # 2. BMO voice / TTS (optional, only warn)
    tts_url = f"http://{tts_host}:{args.tts_port}/health"
    try:
        r = requests.get(tts_url, timeout=4)
        tts_ok = r.status_code < 500
        checks.append(("BMO Voice (TTS)",  tts_ok, f"http://{tts_host}:{args.tts_port}"))
    except Exception as e:
        checks.append(("BMO Voice (TTS)",  None,  f"http://{tts_host}:{args.tts_port} — {e}"))

    # 3. Imports
    checks.append(("Agent imports",     IMPORTS_OK, "ok" if IMPORTS_OK else "using fallback stubs"))

    # --- Print table ---
    col_w = 26
    print()
    print("  +-----------+")
    print("  |   o . o   |    BMO Preflight Check")
    print("  |     -     |    " + time.strftime("%Y-%m-%d %H:%M:%S"))
    print("  |   \\___/   |")
    print("  +-----------+")
    print()
    print(f"  {'SERVICE':<{col_w}}  {'STATUS':<8}  DETAIL")
    print("  " + "-" * 70)
    all_critical_ok = True
    for name, status, detail in checks:
        if status is True:
            icon = "✅ OK   "
        elif status is False:
            icon = "❌ FAIL "
            if name != "BMO Voice (TTS)":   # TTS is optional
                all_critical_ok = False
        else:
            icon = "⚠️  WARN "
        print(f"  {name:<{col_w}}  {icon}  {detail}")
    print("  " + "-" * 70)
    if all_critical_ok:
        print("  All critical services OK — sandbox is ready.\n")
    else:
        print("  One or more critical services are DOWN. Resolve issues above.\n")
    return all_critical_ok


def interactive_mode(args):
    """REPL chat loop."""
    print()
    print("  +-----------+")
    print("  |   ^   ^   |    BMO Test Sandbox")
    print("  |     .     |    Model: " + args.model)
    print("  |   \\___/   |    Host:  " + f"{args.host}:{args.port}")
    print("  +-----------+    TTS:   " + ("ON" if args.tts else "OFF"))
    print("  |  [=====]  |")
    print("  +-----------+")
    print()
    print("  Type a message to test BMO's response.")
    print("  Commands: /quit /emotion <text> /sample <text> /prompt")
    print()

    while True:
        try:
            user_input = input("  You> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Beemo says goodbye!")
            break

        if not user_input:
            continue
        if user_input in ("/quit", "/exit", "exit", "quit"):
            print("  Beemo says goodbye!")
            break

        # Debug commands
        if user_input.startswith("/emotion "):
            text = user_input[9:]
            e, p, s = detect_emotion(text)
            face = FACE_MAP.get(e, "o.o")
            print(f"  {face}  Emotion: {e}, Pitch: {p:+d}, Speed: {s:.2f}x")
            continue

        if user_input.startswith("/sample "):
            text = user_input[8:]
            s = get_sample_path(text)
            r = find_sample_in_response(text) if not s else None
            print(f"  Input match:    {s or 'none'}")
            print(f"  Response match: {r or 'none'}")
            continue

        if user_input == "/prompt":
            print(f"\n{BMO_SYSTEM_PROMPT}\n")
            continue

        run_single(user_input, args.model, args.host, args.port,
                   args.tts, args.tts_host or args.host, args.tts_port)


def batch_mode(args):
    """Run a file of test prompts."""
    with open(args.batch, "r", encoding="utf-8") as f:
        prompts = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    print(f"\n  Running {len(prompts)} test prompts...\n")
    for i, prompt in enumerate(prompts, 1):
        print(f"  [{i}/{len(prompts)}]")
        run_single(prompt, args.model, args.host, args.port,
                   args.tts, args.tts_host or args.host, args.tts_port)
    print(f"\n  Done. {len(prompts)} prompts tested.")


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="BMO Test Sandbox")
    parser.add_argument("--host", default="192.168.2.103", help="Ollama host (default: 192.168.2.103)")
    parser.add_argument("--port", type=int, default=11434, help="Ollama port (default: 11434)")
    parser.add_argument("--model", default=os.getenv("BMO_LLM_MODEL", "qwen3:14b"),
                        help="LLM model (default: qwen3:14b)")
    parser.add_argument("--tts", action="store_true", help="Enable TTS voice generation")
    parser.add_argument("--tts-host", default=None, help="BMO voice host (default: same as --host)")
    parser.add_argument("--tts-port", type=int, default=8100, help="BMO voice port (default: 8100)")
    parser.add_argument("--prompt", type=str, help="Single prompt to test (non-interactive)")
    parser.add_argument("--batch", type=str, help="File of prompts to test (one per line)")
    parser.add_argument("--preflight", action="store_true", help="Check service availability and exit")
    args = parser.parse_args()

    if not IMPORTS_OK:
        print("  Note: Running with fallback stubs (voice_samples_map/bmo_persona not found).")
        print("  For full functionality, run from the project root.\n")

    if args.preflight or args.prompt is None and args.batch is None:
        preflight_ok = run_preflight(args)
        if args.preflight:
            sys.exit(0 if preflight_ok else 1)

    if args.prompt:
        run_single(args.prompt, args.model, args.host, args.port,
                   args.tts, args.tts_host or args.host, args.tts_port)
    elif args.batch:
        batch_mode(args)
    else:
        interactive_mode(args)


if __name__ == "__main__":
    main()
