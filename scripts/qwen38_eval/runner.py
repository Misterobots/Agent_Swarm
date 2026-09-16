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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the deterministic Qwen 3.8 qualification suite.")
    parser.add_argument("--mode", choices=("mock", "live"), default="mock",
                        help="mock is offline and safe; live is reserved for the parent integration adapter")
    parser.add_argument("--report", type=Path, default=Path("artifacts/qwen38-evaluation.json"))
    args = parser.parse_args(argv)
    if args.mode == "live":
        raise SystemExit("live mode is intentionally blocked until the lead delivers the integration contract")
    provider = DeterministicProvider()
    results = all_cases(provider, mode=args.mode)
    write_json_report(args.report, mode=args.mode, results=results)
    print(json.dumps({"mode": args.mode, "passed": sum(r.passed for r in results),
                      "total": len(results), "report": str(args.report)}, indent=2))
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
