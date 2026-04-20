#!/usr/bin/env python3
"""
TTFT (Time-to-First-Token) Benchmark Script
=============================================
Measures latency from request submission to first streamed token.
Run before/after optimization to quantify improvements.

Usage:
    python scripts/benchmark_ttft.py                      # defaults to local Ollama
    python scripts/benchmark_ttft.py --host 192.168.2.103 # test R730
    python scripts/benchmark_ttft.py --rounds 20          # more samples
"""

import argparse
import json
import statistics
import sys
import time
import urllib.request
import urllib.error


PROMPTS = [
    # Short intent-like queries (typical user input)
    "Turn on the living room lights",
    "Generate an image of a sunset over mountains",
    "Write a Python function to sort a list",
    "What's the weather like today?",
    "Explain how SPIRE attestation works",
    # Medium-length queries
    "I need to deploy a new Docker container on the R730 server with GPU passthrough enabled. Can you walk me through the steps?",
    "Create a REST API endpoint that accepts JSON payloads and stores them in PostgreSQL with proper validation",
]


def measure_ttft(host: str, port: int, model: str, prompt: str, timeout: float = 30.0) -> dict:
    """Send a streaming generate request and measure time to first token."""
    url = f"http://{host}:{port}/api/generate"
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {"num_predict": 10},  # Only need a few tokens
    }).encode()

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

    t_start = time.perf_counter()
    ttft = None
    tokens = 0

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for line in resp:
                if not line.strip():
                    continue
                chunk = json.loads(line)
                if chunk.get("response") and ttft is None:
                    ttft = (time.perf_counter() - t_start) * 1000  # ms
                if chunk.get("response"):
                    tokens += 1
                if chunk.get("done"):
                    break
    except urllib.error.URLError as e:
        return {"error": str(e), "prompt": prompt[:50]}
    except Exception as e:
        return {"error": str(e), "prompt": prompt[:50]}

    total_ms = (time.perf_counter() - t_start) * 1000
    return {
        "prompt": prompt[:50],
        "ttft_ms": round(ttft, 1) if ttft else None,
        "total_ms": round(total_ms, 1),
        "tokens": tokens,
    }


def run_benchmark(host: str, port: int, model: str, rounds: int, warmup: bool):
    print(f"TTFT Benchmark: {model} @ {host}:{port}")
    print(f"Rounds: {rounds} | Warmup: {warmup}")
    print("=" * 60)

    # Optional warmup — ensures model is loaded in VRAM
    if warmup:
        print("Warming up model...", end=" ", flush=True)
        result = measure_ttft(host, port, model, "Hello", timeout=60.0)
        if "error" in result:
            print(f"FAILED: {result['error']}")
            sys.exit(1)
        print(f"done ({result.get('ttft_ms', '?')}ms)")
        print()

    all_ttft = []
    for r in range(rounds):
        prompt = PROMPTS[r % len(PROMPTS)]
        result = measure_ttft(host, port, model, prompt)
        if "error" in result:
            print(f"  Round {r+1}: ERROR - {result['error']}")
            continue
        ttft = result["ttft_ms"]
        all_ttft.append(ttft)
        print(f"  Round {r+1:2d}: TTFT={ttft:7.1f}ms  total={result['total_ms']:7.1f}ms  \"{result['prompt']}...\"")

    if not all_ttft:
        print("\nNo successful measurements.")
        return

    print()
    print("=" * 60)
    print(f"Results ({len(all_ttft)} successful rounds):")
    print(f"  Median TTFT:  {statistics.median(all_ttft):7.1f} ms")
    print(f"  Mean TTFT:    {statistics.mean(all_ttft):7.1f} ms")
    print(f"  P95 TTFT:     {sorted(all_ttft)[int(len(all_ttft) * 0.95)]:7.1f} ms")
    print(f"  Min TTFT:     {min(all_ttft):7.1f} ms")
    print(f"  Max TTFT:     {max(all_ttft):7.1f} ms")
    if len(all_ttft) > 1:
        print(f"  Stdev:        {statistics.stdev(all_ttft):7.1f} ms")


def main():
    parser = argparse.ArgumentParser(description="TTFT Benchmark for Ollama models")
    parser.add_argument("--host", default="localhost", help="Ollama host (default: localhost)")
    parser.add_argument("--port", type=int, default=11434, help="Ollama port (default: 11434)")
    parser.add_argument("--model", default="qwen3:14b", help="Model to benchmark (default: qwen3:14b)")
    parser.add_argument("--rounds", type=int, default=10, help="Number of measurement rounds (default: 10)")
    parser.add_argument("--no-warmup", action="store_true", help="Skip warmup (measures cold start)")
    args = parser.parse_args()

    run_benchmark(args.host, args.port, args.model, args.rounds, warmup=not args.no_warmup)


if __name__ == "__main__":
    main()
