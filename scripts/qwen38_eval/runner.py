from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.qwen38_eval.cases import all_cases
from tests.qwen38_eval.harness import DeterministicProvider, write_json_report
from scripts.qwen38_eval.live_adapter import LiveAdapterError, LiveMemexAdapter
from scripts.qwen38_eval.live_cases import live_cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the deterministic Qwen 3.8 qualification suite.")
    parser.add_argument("--mode", choices=("mock", "live"), default="mock",
                        help="mock is offline; live calls the configured Memex dev runtime")
    parser.add_argument("--live", action="store_true",
                        help="required acknowledgement before making live requests")
    parser.add_argument("--base-url", default="http://127.0.0.1:8009")
    parser.add_argument("--interactive", action="store_true",
                        help="allow human approval prerequisites where supported")
    parser.add_argument("--report", type=Path, default=Path("artifacts/qwen38-evaluation.json"))
    args = parser.parse_args(argv)
    if args.mode == "live" and not args.live:
        raise SystemExit("live mode requires --live; no live request was made")
    if args.mode == "live":
        try:
            adapter = LiveMemexAdapter(base_url=args.base_url)
            results = live_cases(adapter, interactive=args.interactive)
        except LiveAdapterError as exc:
            raise SystemExit(f"live evaluation blocked before requests: {exc}") from exc
    else:
        results = all_cases(DeterministicProvider(), mode=args.mode)
    write_json_report(args.report, mode=args.mode, results=results)
    blocked = sum(r.status == "blocked" for r in results)
    failed = sum(r.status == "failed" for r in results)
    print(json.dumps({"mode": args.mode, "passed": sum(r.passed for r in results),
                      "blocked": blocked, "failed": failed, "total": len(results),
                      "report": str(args.report)}, indent=2))
    return 2 if blocked else (1 if failed else 0)


if __name__ == "__main__":
    raise SystemExit(main())
