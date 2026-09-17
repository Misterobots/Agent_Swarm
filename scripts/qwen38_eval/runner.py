from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.qwen38_eval.cases import all_cases
from tests.qwen38_eval.harness import (DeterministicProvider, Observation,
                                        BASELINE_MODEL, RunIdentity, result,
                                        write_json_report)
from scripts.qwen38_eval.live_adapter import LiveAdapterError, LiveMemexAdapter
from scripts.qwen38_eval.live_cases import live_cases, live_smoke_cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the deterministic Qwen 3.8 qualification suite.")
    parser.add_argument("--mode", choices=("mock", "live"), default="mock",
                        help="mock is offline; live calls the configured Memex dev runtime")
    parser.add_argument("--live", action="store_true",
                        help="required acknowledgement before making live requests")
    parser.add_argument("--base-url", default="http://127.0.0.1:8009")
    parser.add_argument("--interactive", action="store_true",
                        help="allow human approval prerequisites where supported")
    parser.add_argument("--fixture-approval", action="store_true",
                        help="exercise deny through the caller-authenticated approval API")
    parser.add_argument("--runs", type=int, default=3,
                        help="sequential positive-suite repetitions in live mode")
    parser.add_argument("--baseline-model", default=BASELINE_MODEL,
                        help="read-only inspected original default model for identical-input baseline")
    parser.add_argument("--stage", choices=("smoke", "exhaustive"), default="smoke",
                        help="smoke runs one bounded gate; exhaustive requires --smoke-passed")
    parser.add_argument("--smoke-passed", action="store_true",
                        help="coordinator acknowledgement that the staged smoke gate passed")
    parser.add_argument("--report", type=Path, default=Path("artifacts/qwen38-evaluation.json"))
    args = parser.parse_args(argv)
    if args.mode == "live" and not args.live:
        raise SystemExit("live mode requires --live; no live request was made")
    if args.mode == "live":
        if args.stage == "exhaustive" and not args.smoke_passed:
            raise SystemExit("exhaustive stage requires --smoke-passed after the smoke gate")
        try:
            adapter = LiveMemexAdapter(base_url=args.base_url)
            if args.runs < 1:
                raise SystemExit("--runs must be positive")
            results = []
            run_count = args.runs if args.stage == "exhaustive" else 1
            case_runner = live_cases if args.stage == "exhaustive" else live_smoke_cases
            for run_number in range(1, run_count + 1):
                run_results = case_runner(adapter, interactive=args.interactive,
                                          fixture_approval=args.fixture_approval)
                for item in run_results:
                    item.details["positive_run_number"] = run_number
                results.extend(run_results)
            baseline_adapter = LiveMemexAdapter(base_url=args.base_url, model=args.baseline_model,
                                                 send_context_profile=False,
                                                 vision_route="legacy")
            for run_number in range(1, run_count + 1):
                baseline_results = case_runner(baseline_adapter, interactive=args.interactive,
                                              fixture_approval=args.fixture_approval)
                for item in baseline_results:
                    item.mode = "baseline"
                    item.details.update({"baseline_model": args.baseline_model,
                                         "baseline_source": "read-only dev runtime config",
                                         "identical_fixture_replay": True,
                                         "baseline_run_number": run_number})
                results.extend(baseline_results)
        except LiveAdapterError as exc:
            raise SystemExit(f"live evaluation blocked before requests: {exc}") from exc
    else:
        results = all_cases(DeterministicProvider(), mode=args.mode)
    blocked = sum(r.status == "blocked" for r in results)
    failed = sum(r.status == "failed" for r in results)
    extra = {}
    if args.mode == "live" and args.stage == "exhaustive":
        extra = {
            "stage": args.stage,
            "runs": args.runs,
            "smoke_passed": args.smoke_passed,
            "baseline_model": args.baseline_model,
            "summary": {
                "total_results": len(results),
                "passed": sum(r.passed for r in results),
                "blocked": blocked,
                "failed": failed,
            },
        }
    write_json_report(args.report, mode=args.mode, results=results, **extra)
    print(json.dumps({"mode": args.mode, "passed": sum(r.passed for r in results),
                      "blocked": blocked, "failed": failed, "total": len(results),
                      "report": str(args.report)}, indent=2))
    return 2 if blocked else (1 if failed else 0)


if __name__ == "__main__":
    raise SystemExit(main())
