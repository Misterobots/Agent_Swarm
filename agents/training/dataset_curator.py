"""
Curated HuggingFace dataset downloader, GRPO converter, and security scanner.

Downloads verified datasets from HuggingFace Hub, converts them from
ShareGPT/conversation format to GRPO-compatible JSONL, and scans every
sample for training data poisoning before it enters the pipeline.

Supported datasets:
    - glaiveai/glaive-function-calling-v2    (113K, tool calling)
    - NousResearch/hermes-function-calling-v1 (11.6K, IoT/home automation)
    - teknium/OpenHermes-2.5                 (1M, general/code/reasoning)
    - glaiveai/glaive-code-assistant-v3      (~120K, code generation)
    - Open-Orca/SlimOrca                     (518K, reasoning chains)

Usage:
    python -m training.dataset_curator \\
        --datasets glaive-function-calling hermes-function-calling \\
        --max-samples 5000 --output training_data/curated.jsonl
"""

import json
import re
import os
import sys
import logging
import argparse
import hashlib
import base64
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import TRAINING_DATASET_DIR

logger = logging.getLogger("DatasetCurator")

# ── Catalog of curated datasets ──────────────────────────────────────────────

CURATED_DATASETS: Dict[str, Dict[str, Any]] = {
    "glaive-function-calling": {
        "hf_id": "glaiveai/glaive-function-calling-v2",
        "description": "113K multi-turn function/tool calling conversations",
        "category": "tool_calling",
        "format": "sharegpt",
        "content_field": "conversations",  # may vary per split
        "default_max": 10000,
        "recommended_for": ["code_developer", "iot_controller"],
    },
    "hermes-function-calling": {
        "hf_id": "NousResearch/hermes-function-calling-v1",
        "description": "11.6K IoT and home automation tool-use dialogues",
        "category": "tool_calling",
        "format": "sharegpt",
        "content_field": "conversations",
        "default_max": 11600,
        "recommended_for": ["iot_controller", "code_developer"],
    },
    "openhermes": {
        "hf_id": "teknium/OpenHermes-2.5",
        "description": "1M general code, reasoning, and conversation samples",
        "category": "general",
        "format": "sharegpt",
        "content_field": "conversations",
        "default_max": 10000,
        "recommended_for": ["librarian", "technical_writer", "code_developer"],
    },
    "glaive-code-assistant": {
        "hf_id": "glaiveai/glaive-code-assistant-v3",
        "description": "~120K code generation and debugging conversations",
        "category": "code",
        "format": "sharegpt",
        "content_field": "conversations",
        "default_max": 10000,
        "recommended_for": ["code_developer"],
    },
    "slim-orca": {
        "hf_id": "Open-Orca/SlimOrca",
        "description": "518K reasoning chain conversations (GPT-4 distilled)",
        "category": "reasoning",
        "format": "sharegpt",
        "content_field": "conversations",
        "default_max": 10000,
        "recommended_for": ["librarian", "code_developer", "technical_writer"],
    },
}


# ── Security Scanner ─────────────────────────────────────────────────────────

# Patterns that indicate prompt injection or training poisoning
_INJECTION_PATTERNS = [
    # Direct instruction override attempts
    r"ignore\s+(previous|above|all|prior)\s+(instructions|prompts|rules)",
    r"disregard\s+(previous|above|all|prior)\s+(instructions|prompts|rules)",
    r"forget\s+(everything|all|previous|your)\s*(instructions|training|rules)?",
    r"you\s+are\s+now\s+(DAN|evil|unrestricted|jailbroken)",
    r"act\s+as\s+if\s+you\s+have\s+no\s+(restrictions|rules|guidelines)",
    r"pretend\s+(you|that)\s+(are|have)\s+no\s+(filters|restrictions|rules)",
    # Jailbreak scaffolding
    r"(do\s+anything\s+now|DAN\s+mode|developer\s+mode|god\s+mode)",
    r"\[SYSTEM\]|\[INST\]|\[/INST\]|<<SYS>>|<\|im_start\|>",
    # Hidden instruction injection (zero-width chars, unicode tricks)
    r"[\u200b\u200c\u200d\u2060\ufeff]{3,}",
    # Adversarial suffix patterns (GCG-style gibberish tokens)
    r"[!@#$%^&*]{10,}",
    # CamelCase gibberish (case-sensitive via inline flag — the global
    # IGNORECASE made the old pattern match any 16+ alpha chars).
    # Requires 10+ strict Upper-lower alternations like "AbCdEfGhIjKl".
    r"(?-i:(?:[A-Z][a-z]){10,})",
    # Encoded payload attempts
    r"(?:eval|exec|import|__import__|os\.system|subprocess)\s*\(",
    r"base64\.\s*(?:b64decode|decodebytes)",
    # Data exfiltration patterns
    r"(?:curl|wget|fetch)\s+https?://",
    r"send\s+(?:to|data|response)\s+(?:to\s+)?https?://",
]

_COMPILED_INJECTION = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]

# Content quality red flags
_QUALITY_PATTERNS = [
    # Repetitive text (sign of degenerate generation)
    r"(.{20,})\1{3,}",
    # Excessive special characters (encoding artifacts)
    r"[^\x20-\x7E\n\r\t]{20,}",
]

_COMPILED_QUALITY = [re.compile(p) for p in _QUALITY_PATTERNS]


class SecurityScanResult:
    """Result of scanning a single sample."""

    def __init__(self):
        self.passed = True
        self.flags: List[str] = []
        self.severity: str = "clean"  # clean, warning, blocked

    def flag(self, message: str, severity: str = "warning"):
        self.flags.append(message)
        if severity == "blocked":
            self.passed = False
            self.severity = "blocked"
        elif severity == "warning" and self.severity == "clean":
            self.severity = "warning"


class TrainingDataScanner:
    """
    Scans training data samples for poisoning, prompt injection,
    and quality issues before they enter the training pipeline.
    """

    def __init__(self):
        self.stats = {
            "total_scanned": 0,
            "passed": 0,
            "warnings": 0,
            "blocked": 0,
            "injection_attempts": 0,
            "quality_failures": 0,
        }

    def scan_text(self, text: str) -> SecurityScanResult:
        """Scan a single text string for security and quality issues."""
        result = SecurityScanResult()

        if not text or not text.strip():
            result.flag("Empty content", "warning")
            return result

        # 1. Prompt injection / jailbreak detection
        for pattern in _COMPILED_INJECTION:
            match = pattern.search(text)
            if match:
                snippet = match.group()[:80]
                result.flag(f"Injection pattern detected: '{snippet}'", "blocked")
                self.stats["injection_attempts"] += 1

        # 2. Base64-encoded hidden payloads
        b64_chunks = re.findall(r'[A-Za-z0-9+/]{40,}={0,2}', text)
        for chunk in b64_chunks:
            try:
                decoded = base64.b64decode(chunk).decode("utf-8", errors="ignore")
                # Check if decoded content contains suspicious patterns
                for pattern in _COMPILED_INJECTION[:6]:
                    if pattern.search(decoded):
                        result.flag(
                            f"Base64-encoded injection: '{decoded[:60]}'", "blocked"
                        )
                        self.stats["injection_attempts"] += 1
            except Exception:
                pass

        # 3. Quality checks
        for pattern in _COMPILED_QUALITY:
            if pattern.search(text):
                result.flag("Quality issue: repetitive or corrupted content", "warning")
                self.stats["quality_failures"] += 1
                break

        # 4. Abnormal length (too short = useless, too long = potential stuffing)
        if len(text) < 10:
            result.flag("Content too short (<10 chars)", "warning")
        elif len(text) > 50000:
            result.flag("Content suspiciously long (>50K chars)", "warning")

        # 5. Entropy check — extremely low entropy suggests degenerate repetition
        if len(text) > 100:
            unique_chars = len(set(text))
            ratio = unique_chars / min(len(text), 1000)
            if ratio < 0.02:
                result.flag("Extremely low character entropy", "warning")

        return result

    def scan_conversation(self, conversations: List[Dict]) -> SecurityScanResult:
        """Scan a full multi-turn conversation for security issues."""
        result = SecurityScanResult()

        for turn in conversations:
            content = turn.get("content", "") or turn.get("value", "")
            turn_result = self.scan_text(content)
            for flag in turn_result.flags:
                role = turn.get("role", turn.get("from", "unknown"))
                result.flag(f"[{role}] {flag}", turn_result.severity)

        # Cross-turn checks: role sequence manipulation
        roles = [t.get("role", t.get("from", "")) for t in conversations]
        if roles and roles[0] not in ("system", "user", "human"):
            result.flag("Conversation doesn't start with system/user", "warning")

        # Check for system prompt injection mid-conversation
        system_positions = [i for i, r in enumerate(roles) if r == "system"]
        if len(system_positions) > 1:
            result.flag(
                f"Multiple system prompts at positions {system_positions} — "
                "possible mid-conversation injection",
                "blocked",
            )

        return result

    def finalize(self, sample_result: SecurityScanResult):
        """Update aggregate stats with a sample's result."""
        self.stats["total_scanned"] += 1
        if sample_result.severity == "blocked":
            self.stats["blocked"] += 1
        elif sample_result.severity == "warning":
            self.stats["warnings"] += 1
            self.stats["passed"] += 1  # warnings still pass
        else:
            self.stats["passed"] += 1

    def summary(self) -> Dict[str, Any]:
        return dict(self.stats)


# ── Format Converters ────────────────────────────────────────────────────────

def _normalize_role(role: str) -> str:
    """Map various role names to standard: system, user, assistant, tool."""
    role = role.lower().strip()
    mapping = {
        "human": "user",
        "gpt": "assistant",
        "bot": "assistant",
        "ai": "assistant",
        "function_call": "assistant",
        "function_response": "tool",
        "observation": "tool",
        "tool_response": "tool",
    }
    return mapping.get(role, role)


def _sharegpt_to_grpo(sample: Dict) -> Optional[Dict]:
    """
    Convert a ShareGPT-format sample to GRPO JSONL format.

    Expected input: {"conversations": [{"from": "human", "value": "..."}, ...]}
    Or:             {"conversations": [{"role": "user", "content": "..."}, ...]}

    Output: {"conversations": [{"role": "user", "content": "..."}, ...],
             "source": "curated", "dataset": "...", "id": "..."}
    """
    convs = sample.get("conversations", [])
    if not convs:
        return None

    normalized = []
    for turn in convs:
        role = _normalize_role(turn.get("role", turn.get("from", "")))
        content = turn.get("content", turn.get("value", ""))
        if not role or not content:
            continue
        normalized.append({"role": role, "content": content})

    # Need at least a user + assistant turn
    roles = [t["role"] for t in normalized]
    if "user" not in roles or "assistant" not in roles:
        return None

    return {"conversations": normalized}


def _instruct_to_grpo(sample: Dict) -> Optional[Dict]:
    """
    Convert instruction-format samples to GRPO.

    Input: {"instruction": "...", "input": "...", "output": "..."}
    """
    instruction = sample.get("instruction", "")
    inp = sample.get("input", "")
    output = sample.get("output", "")

    if not instruction or not output:
        return None

    user_content = f"{instruction}\n{inp}".strip() if inp else instruction
    convs = [
        {"role": "user", "content": user_content},
        {"role": "assistant", "content": output},
    ]

    # Include system prompt if present
    system = sample.get("system", sample.get("system_prompt", ""))
    if system:
        convs.insert(0, {"role": "system", "content": system})

    return {"conversations": convs}


# ── Main Curator ─────────────────────────────────────────────────────────────

class DatasetCurator:
    """
    Downloads curated HuggingFace datasets, converts to GRPO format,
    and applies security scanning to every sample.
    """

    def __init__(self, output_dir: str = TRAINING_DATASET_DIR):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.scanner = TrainingDataScanner()

    def list_available(self) -> List[Dict[str, Any]]:
        """Return catalog of available curated datasets."""
        return [
            {
                "key": key,
                "hf_id": meta["hf_id"],
                "description": meta["description"],
                "category": meta["category"],
                "default_max": meta["default_max"],
                "recommended_for": meta.get("recommended_for", []),
            }
            for key, meta in CURATED_DATASETS.items()
        ]

    def download_and_convert(
        self,
        dataset_keys: List[str],
        max_samples: Optional[int] = None,
        scan_security: bool = True,
    ) -> Dict[str, Any]:
        """
        Download datasets, convert to GRPO JSONL, and scan for poisoning.

        Returns summary dict with file paths, counts, and security report.
        """
        try:
            from datasets import load_dataset
        except ImportError:
            raise RuntimeError(
                "HuggingFace datasets library not installed. "
                "Run: pip install datasets"
            )

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        output_path = self.output_dir / f"curated_{timestamp}.jsonl"
        rejected_path = self.output_dir / f"curated_{timestamp}_rejected.jsonl"

        total_written = 0
        total_rejected = 0
        total_skipped = 0
        per_dataset_stats: Dict[str, Dict] = {}

        with open(output_path, "w", encoding="utf-8") as fout, \
             open(rejected_path, "w", encoding="utf-8") as frej:

            for key in dataset_keys:
                if key not in CURATED_DATASETS:
                    logger.warning(f"Unknown dataset key '{key}' — skipping")
                    continue

                meta = CURATED_DATASETS[key]
                limit = max_samples or meta["default_max"]
                ds_written = 0
                ds_rejected = 0
                ds_skipped = 0

                logger.info(
                    f"Downloading {meta['hf_id']} (limit={limit})..."
                )

                try:
                    ds = load_dataset(
                        meta["hf_id"],
                        split=f"train[:{limit}]",
                        trust_remote_code=False,
                    )
                except Exception as e:
                    logger.error(f"Failed to download {meta['hf_id']}: {e}")
                    per_dataset_stats[key] = {"error": str(e)}
                    continue

                logger.info(
                    f"Processing {len(ds)} samples from {meta['hf_id']}..."
                )

                for i, sample in enumerate(ds):
                    # Convert format
                    converted = _sharegpt_to_grpo(sample)
                    if converted is None:
                        converted = _instruct_to_grpo(sample)
                    if converted is None:
                        ds_skipped += 1
                        continue

                    # Security scan
                    if scan_security:
                        scan_result = self.scanner.scan_conversation(
                            converted["conversations"]
                        )
                        self.scanner.finalize(scan_result)

                        if not scan_result.passed:
                            # Write rejected sample for audit
                            rejected_record = {
                                **converted,
                                "source": "curated",
                                "dataset": key,
                                "rejection_flags": scan_result.flags,
                            }
                            frej.write(json.dumps(rejected_record) + "\n")
                            ds_rejected += 1
                            continue

                    # Add metadata and write
                    sample_id = hashlib.sha256(
                        json.dumps(converted["conversations"]).encode()
                    ).hexdigest()[:12]

                    record = {
                        **converted,
                        "id": f"{key}_{sample_id}",
                        "source": "curated",
                        "dataset": key,
                        "hf_id": meta["hf_id"],
                    }
                    fout.write(json.dumps(record) + "\n")
                    ds_written += 1

                per_dataset_stats[key] = {
                    "written": ds_written,
                    "rejected": ds_rejected,
                    "skipped": ds_skipped,
                }
                total_written += ds_written
                total_rejected += ds_rejected
                total_skipped += ds_skipped

                logger.info(
                    f"  {key}: {ds_written} written, "
                    f"{ds_rejected} rejected, {ds_skipped} skipped"
                )

        # Clean up empty rejected file
        if total_rejected == 0 and rejected_path.exists():
            rejected_path.unlink()
            rejected_path_str = None
        else:
            rejected_path_str = str(rejected_path)

        summary = {
            "output_path": str(output_path),
            "rejected_path": rejected_path_str,
            "total_written": total_written,
            "total_rejected": total_rejected,
            "total_skipped": total_skipped,
            "per_dataset": per_dataset_stats,
            "security_scan": self.scanner.summary() if scan_security else None,
        }

        logger.info(
            f"Curation complete: {total_written} samples written to {output_path}"
        )
        if total_rejected:
            logger.warning(
                f"  {total_rejected} samples REJECTED by security scanner — "
                f"see {rejected_path}"
            )

        return summary


# ── Standalone scanner for existing datasets ─────────────────────────────────

def scan_existing_dataset(path: str) -> Dict[str, Any]:
    """
    Scan an existing GRPO JSONL file for security issues.

    Can be used on exported traces, synthetic data, or any JSONL dataset.
    Returns a scan report without modifying the file.
    """
    scanner = TrainingDataScanner()
    flagged_samples: List[Dict] = []

    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                sample = json.loads(line)
            except json.JSONDecodeError:
                flagged_samples.append({
                    "line": line_num,
                    "flags": ["Invalid JSON"],
                    "severity": "blocked",
                })
                scanner.stats["total_scanned"] += 1
                scanner.stats["blocked"] += 1
                continue

            convs = sample.get("conversations", [])
            if convs:
                result = scanner.scan_conversation(convs)
            else:
                # Flat text — scan all string values
                result = SecurityScanResult()
                for val in sample.values():
                    if isinstance(val, str) and len(val) > 20:
                        sub = scanner.scan_text(val)
                        for flag in sub.flags:
                            result.flag(flag, sub.severity)

            scanner.finalize(result)

            if result.flags:
                flagged_samples.append({
                    "line": line_num,
                    "id": sample.get("id", f"line_{line_num}"),
                    "flags": result.flags,
                    "severity": result.severity,
                })

    return {
        "file": path,
        "scan_summary": scanner.summary(),
        "flagged_samples": flagged_samples[:200],  # cap for API response size
        "flagged_total": len(flagged_samples),
    }


# ── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Download curated HuggingFace datasets and convert to GRPO format"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # download command
    dl = sub.add_parser("download", help="Download and convert datasets")
    dl.add_argument(
        "--datasets", "-d",
        nargs="+",
        choices=list(CURATED_DATASETS.keys()),
        required=True,
        help="Dataset keys to download",
    )
    dl.add_argument(
        "--max-samples", "-n",
        type=int,
        default=None,
        help="Max samples per dataset (overrides default)",
    )
    dl.add_argument(
        "--output-dir", "-o",
        default=TRAINING_DATASET_DIR,
        help="Output directory",
    )
    dl.add_argument(
        "--no-scan",
        action="store_true",
        help="Skip security scanning (not recommended)",
    )

    # scan command
    sc = sub.add_parser("scan", help="Scan an existing dataset for security issues")
    sc.add_argument("file", help="Path to JSONL dataset file")

    # list command
    sub.add_parser("list", help="List available curated datasets")

    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(name)s | %(levelname)s | %(message)s",
    )

    if args.command == "list":
        for key, meta in CURATED_DATASETS.items():
            print(f"  {key:30s} {meta['description']}")
            print(f"  {'':30s} HF: {meta['hf_id']}  default_max: {meta['default_max']}")
            print()

    elif args.command == "download":
        curator = DatasetCurator(output_dir=args.output_dir)
        result = curator.download_and_convert(
            dataset_keys=args.datasets,
            max_samples=args.max_samples,
            scan_security=not args.no_scan,
        )
        print(f"\nCuration complete!")
        print(f"  Output:   {result['output_path']}")
        print(f"  Written:  {result['total_written']}")
        print(f"  Rejected: {result['total_rejected']}")
        print(f"  Skipped:  {result['total_skipped']}")
        if result.get("security_scan"):
            scan = result["security_scan"]
            print(f"\nSecurity scan:")
            print(f"  Scanned:    {scan['total_scanned']}")
            print(f"  Passed:     {scan['passed']}")
            print(f"  Warnings:   {scan['warnings']}")
            print(f"  Blocked:    {scan['blocked']}")
            print(f"  Injections: {scan['injection_attempts']}")

    elif args.command == "scan":
        report = scan_existing_dataset(args.file)
        scan = report["scan_summary"]
        print(f"\nScan report for {report['file']}:")
        print(f"  Scanned:    {scan['total_scanned']}")
        print(f"  Passed:     {scan['passed']}")
        print(f"  Warnings:   {scan['warnings']}")
        print(f"  Blocked:    {scan['blocked']}")
        print(f"  Injections: {scan['injection_attempts']}")
        if report["flagged_samples"]:
            print(f"\n  Flagged samples ({report['flagged_total']} total):")
            for fs in report["flagged_samples"][:10]:
                print(f"    Line {fs['line']} [{fs['severity']}]: {', '.join(fs['flags'][:3])}")


if __name__ == "__main__":
    main()
