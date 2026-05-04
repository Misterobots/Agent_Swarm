#!/usr/bin/env python3
"""
Hive Functional Test Suite — post qwen3.6:27b upgrade
Tests core chat, code gen, routing, and error handling.
Run on Turing: python3 /tmp/hive_functional_test.py
"""

import urllib.request
import urllib.error
import json
import time
import subprocess
import sys

BASE = "http://localhost:8008"
RESULTS = []

def chat(prompt, label="", timeout=90):
    """Send non-streaming chat request, return (content, elapsed_s, error)"""
    data = {
        "model": "qwen3.6:27b",
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BASE}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            elapsed = time.time() - t0
        parsed = json.loads(raw)
        content = parsed.get("choices", [{}])[0].get("message", {}).get("content", "")
        return content, elapsed, None
    except urllib.error.HTTPError as e:
        return "", time.time() - t0, f"HTTP {e.code}: {e.read().decode()[:200]}"
    except Exception as e:
        return "", time.time() - t0, str(e)


def run_test(number, label, prompt, checker=None, timeout=90):
    print(f"\n{'='*60}")
    print(f"TEST {number}: {label}")
    print(f"{'='*60}")
    content, elapsed, error = chat(prompt, timeout=timeout)
    
    if error:
        status = "FAIL"
        detail = error
    else:
        status = "PASS"
        detail = content[:500] if content else "(empty)"
        if checker:
            check_result = checker(content)
            if not check_result:
                status = "WARN"
    
    print(f"STATUS : {status}")
    print(f"TIME   : {elapsed:.2f}s")
    print(f"CONTENT: {detail}")
    
    RESULTS.append({
        "test": number,
        "label": label,
        "status": status,
        "time_s": round(elapsed, 2),
        "content_preview": detail[:200],
    })
    return status != "FAIL"


# ── TEST 1: Health Check ──────────────────────────────────────────────────────
print("\n" + "="*60)
print("TEST 1: Health Check (GET /)")
print("="*60)
try:
    req = urllib.request.Request(f"{BASE}/")
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=10) as resp:
        body = json.loads(resp.read().decode())
        elapsed = time.time() - t0
    status = "PASS" if body.get("status") == "online" else "WARN"
    print(f"STATUS : {status}")
    print(f"TIME   : {elapsed:.2f}s")
    print(f"CONTENT: {body}")
    RESULTS.append({"test": 1, "label": "Health Check", "status": status, "time_s": round(elapsed, 2), "content_preview": str(body)})
except Exception as e:
    print(f"STATUS : FAIL\nERROR  : {e}")
    RESULTS.append({"test": 1, "label": "Health Check", "status": "FAIL", "time_s": 0, "content_preview": str(e)})


# ── TEST 2: Simple Conversation ───────────────────────────────────────────────
run_test(
    2, "Simple Conversation",
    "Hello! Reply in exactly one sentence: what AI model are you?",
    checker=lambda c: len(c) > 10
)

# ── TEST 3: Python Code Generation ───────────────────────────────────────────
run_test(
    3, "Python Code Generation",
    "Write a Python function called `sort_list` that takes a list of integers and returns them sorted in ascending order. Return only the code, no explanation.",
    checker=lambda c: "def sort_list" in c or "sort" in c.lower()
)

# ── TEST 4: Reasoning / Research ─────────────────────────────────────────────
run_test(
    4, "Reasoning / Research",
    "What is the capital city of France? Answer in one word.",
    checker=lambda c: "paris" in c.lower()
)

# ── TEST 5: Long Context Handling ─────────────────────────────────────────────
run_test(
    5, "Long Context / Document Summary",
    "Summarize the following text in 2 sentences:\n\nArtificial intelligence (AI) is intelligence demonstrated by machines, as opposed to the natural intelligence displayed by animals including humans. AI research has been defined as the field of study of intelligent agents, which refers to any system that perceives its environment and takes actions that maximize its chance of achieving its goals. The term may also be applied to any machine that exhibits traits associated with a human mind such as learning and problem-solving.",
    checker=lambda c: len(c) > 20
)

# ── TEST 6: grpc/infer endpoint ───────────────────────────────────────────────
print(f"\n{'='*60}")
print("TEST 6: gRPC classify endpoint")
print("="*60)
try:
    data = {"text": "Write a Python script to list all files in a directory"}
    body = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{BASE}/api/v1/grpc/classify",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=20) as resp:
        result = json.loads(resp.read().decode())
        elapsed = time.time() - t0
    status = "PASS"
    print(f"STATUS : {status}")
    print(f"TIME   : {elapsed:.2f}s")
    print(f"CONTENT: {result}")
    RESULTS.append({"test": 6, "label": "gRPC classify", "status": status, "time_s": round(elapsed, 2), "content_preview": str(result)[:200]})
except urllib.error.HTTPError as e:
    body_text = e.read().decode()[:300]
    print(f"STATUS : FAIL\nHTTP {e.code}: {body_text}")
    RESULTS.append({"test": 6, "label": "gRPC classify", "status": "FAIL", "time_s": 0, "content_preview": body_text})
except Exception as e:
    print(f"STATUS : FAIL\nERROR  : {e}")
    RESULTS.append({"test": 6, "label": "gRPC classify", "status": "FAIL", "time_s": 0, "content_preview": str(e)})

# ── TEST 7: VRAM check on Turing ─────────────────────────────────────────────
print(f"\n{'='*60}")
print("TEST 7: GPU / VRAM status on Turing")
print("="*60)
try:
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=name,memory.used,memory.free,memory.total", "--format=csv,noheader"],
        capture_output=True, text=True, timeout=10
    )
    if result.returncode == 0:
        print(f"STATUS : PASS")
        print(f"GPU    : {result.stdout.strip()}")
        RESULTS.append({"test": 7, "label": "GPU VRAM", "status": "PASS", "time_s": 0, "content_preview": result.stdout.strip()})
    else:
        print(f"STATUS : WARN (no nvidia-smi or no GPU)")
        RESULTS.append({"test": 7, "label": "GPU VRAM", "status": "WARN", "time_s": 0, "content_preview": "no GPU on Turing"})
except Exception as e:
    print(f"STATUS : WARN\nNOTE   : {e}")
    RESULTS.append({"test": 7, "label": "GPU VRAM", "status": "WARN", "time_s": 0, "content_preview": str(e)})

# ── TEST 8: Config verification ───────────────────────────────────────────────
print(f"\n{'='*60}")
print("TEST 8: Config — PRIMARY_MODEL in agent_runtime")
print("="*60)
try:
    result = subprocess.run(
        ["docker", "exec", "agent_runtime", "grep", "-r", "qwen3.6:27b", "/app/agents/config.py"],
        capture_output=True, text=True, timeout=10
    )
    found = "qwen3.6:27b" in result.stdout
    status = "PASS" if found else "FAIL"
    print(f"STATUS : {status}")
    print(f"MATCH  : {result.stdout.strip()[:300]}")
    RESULTS.append({"test": 8, "label": "Config PRIMARY_MODEL", "status": status, "time_s": 0, "content_preview": result.stdout.strip()[:200]})
except Exception as e:
    print(f"STATUS : FAIL\nERROR  : {e}")
    RESULTS.append({"test": 8, "label": "Config PRIMARY_MODEL", "status": "FAIL", "time_s": 0, "content_preview": str(e)})

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'='*60}")
print("SUMMARY")
print("="*60)
passed = sum(1 for r in RESULTS if r["status"] == "PASS")
warned = sum(1 for r in RESULTS if r["status"] == "WARN")
failed = sum(1 for r in RESULTS if r["status"] == "FAIL")
total_chat_time = sum(r["time_s"] for r in RESULTS if r["test"] in [2, 3, 4, 5])
avg_chat_time = total_chat_time / 4 if total_chat_time else 0

print(f"PASS: {passed} | WARN: {warned} | FAIL: {failed} | TOTAL: {len(RESULTS)}")
print(f"Avg chat response time: {avg_chat_time:.2f}s")
print()
for r in RESULTS:
    icon = "✓" if r["status"] == "PASS" else ("!" if r["status"] == "WARN" else "✗")
    print(f"  [{icon}] T{r['test']:02d} {r['label']:<30} {r['time_s']:>5.1f}s  {r['status']}")

# Save results JSON
output = {
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "model": "qwen3.6:27b",
    "passed": passed,
    "warned": warned,
    "failed": failed,
    "avg_chat_time_s": round(avg_chat_time, 2),
    "tests": RESULTS
}
with open("/tmp/hive_test_results.json", "w") as f:
    json.dump(output, f, indent=2)
print(f"\nResults saved to /tmp/hive_test_results.json")
