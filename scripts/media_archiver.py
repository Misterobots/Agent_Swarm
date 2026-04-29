"""
Media Archival System for Memex
Compresses and archives generated media older than 30 days.

Archives are stored server-side only and not accessible via Memex UI.
Retention policy: Media active for 30 days, then compressed and archived.

Usage:
    python media_archiver.py --dry-run  # Preview what would be archived
    python media_archiver.py            # Execute archival
"""

import argparse
import gzip
import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("media_archiver.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MediaArchiver")

# Configuration
ARCHIVE_AGE_DAYS = int(os.getenv("MEDIA_ARCHIVE_AGE_DAYS", "30"))
DELIVERED_ARTIFACTS_DIR = Path(os.getenv("DELIVERED_ARTIFACTS_DIR", "/workspace/delivered_artifacts"))
ARCHIVE_ROOT = Path(os.getenv("MEDIA_ARCHIVE_ROOT", "/workspace/media_archives"))
COMFY_OUTPUT_DIR = Path("/app/comfy_io/output")

# Media directories to archive
MEDIA_DIRS = [
    DELIVERED_ARTIFACTS_DIR,
    COMFY_OUTPUT_DIR,
]


def get_file_age_days(file_path: Path) -> float:
    """Get the age of a file in days based on its modification time."""
    mtime = file_path.stat().st_mtime
    age_seconds = time.time() - mtime
    return age_seconds / (24 * 3600)


def should_archive(file_path: Path, archive_age_days: int) -> bool:
    """
    Determine if a file should be archived.
    
    Rules:
    - File must be older than archive_age_days
    - File must be a media file (image, video, audio, 3D model)
    - Metadata sidecar files (.json) are archived alongside their media files
    """
    if not file_path.is_file():
        return False
    
    # Skip already compressed files
    if file_path.suffix == ".gz":
        return False
    
    # Check age
    age_days = get_file_age_days(file_path)
    if age_days < archive_age_days:
        return False
    
    # Media file extensions
    media_extensions = {
        ".png", ".jpg", ".jpeg", ".gif", ".webp",  # Images
        ".mp4", ".webm", ".mov", ".avi",  # Video
        ".mp3", ".wav", ".ogg", ".m4a",  # Audio
        ".glb", ".gltf", ".obj", ".stl", ".3mf",  # 3D models
        ".json"  # Metadata sidecars
    }
    
    return file_path.suffix.lower() in media_extensions


def compress_file(source: Path, dest: Path) -> Dict[str, Any]:
    """
    Compress a file using gzip.
    
    Returns metadata about the compression.
    """
    original_size = source.stat().st_size
    
    dest.parent.mkdir(parents=True, exist_ok=True)
    
    with open(source, 'rb') as f_in:
        with gzip.open(dest, 'wb', compresslevel=9) as f_out:
            shutil.copyfileobj(f_in, f_out)
    
    compressed_size = dest.stat().st_size
    compression_ratio = compressed_size / original_size if original_size > 0 else 0
    
    return {
        "original_size": original_size,
        "compressed_size": compressed_size,
        "compression_ratio": compression_ratio,
        "savings_percent": (1 - compression_ratio) * 100,
    }


def archive_media_file(file_path: Path, archive_root: Path, dry_run: bool = False) -> Dict[str, Any]:
    """
    Archive a media file by compressing and moving it to the archive directory.
    
    Maintains directory structure: archive_root/YYYY-MM/source_dir/filename.ext.gz
    """
    # Determine source directory name (delivered_artifacts, output, etc.)
    try:
        source_dir_name = file_path.parent.name
    except:
        source_dir_name = "unknown"
    
    # Create archive path with year-month organization
    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc)
    year_month = file_mtime.strftime("%Y-%m")
    
    archive_path = archive_root / year_month / source_dir_name / f"{file_path.name}.gz"
    
    result = {
        "source": str(file_path),
        "archive_path": str(archive_path),
        "age_days": get_file_age_days(file_path),
        "dry_run": dry_run,
    }
    
    if dry_run:
        result["status"] = "would_archive"
        result["original_size"] = file_path.stat().st_size
        return result
    
    try:
        # Compress and move
        compression_info = compress_file(file_path, archive_path)
        result.update(compression_info)
        
        # Copy original file timestamps to archive
        stat_info = file_path.stat()
        os.utime(archive_path, (stat_info.st_atime, stat_info.st_mtime))
        
        # Remove original file
        file_path.unlink()
        
        result["status"] = "archived"
        logger.info(
            f"Archived: {file_path.name} "
            f"({compression_info['original_size'] / 1024:.1f} KB → "
            f"{compression_info['compressed_size'] / 1024:.1f} KB, "
            f"{compression_info['savings_percent']:.1f}% savings)"
        )
        
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        logger.error(f"Failed to archive {file_path}: {e}")
    
    return result


def archive_media_directory(
    media_dir: Path,
    archive_root: Path,
    archive_age_days: int,
    dry_run: bool = False
) -> List[Dict[str, Any]]:
    """
    Archive all eligible media files in a directory.
    """
    if not media_dir.exists():
        logger.warning(f"Media directory not found: {media_dir}")
        return []
    
    results = []
    
    logger.info(f"Scanning: {media_dir}")
    
    for file_path in media_dir.rglob("*"):
        if should_archive(file_path, archive_age_days):
            result = archive_media_file(file_path, archive_root, dry_run=dry_run)
            results.append(result)
    
    return results


def generate_archive_report(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate a summary report of the archival operation."""
    total_files = len(results)
    
    if total_files == 0:
        return {"total_files": 0, "message": "No files to archive"}
    
    archived_files = [r for r in results if r["status"] == "archived"]
    error_files = [r for r in results if r["status"] == "error"]
    would_archive_files = [r for r in results if r["status"] == "would_archive"]
    
    total_original_size = sum(r.get("original_size", 0) for r in results)
    total_compressed_size = sum(r.get("compressed_size", 0) for r in archived_files)
    
    report = {
        "total_files": total_files,
        "archived": len(archived_files),
        "errors": len(error_files),
        "would_archive": len(would_archive_files),
        "total_original_size_mb": total_original_size / (1024 * 1024),
        "total_compressed_size_mb": total_compressed_size / (1024 * 1024),
        "total_savings_mb": (total_original_size - total_compressed_size) / (1024 * 1024),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    
    if total_original_size > 0:
        report["average_compression_ratio"] = total_compressed_size / total_original_size
        report["total_savings_percent"] = (1 - report["average_compression_ratio"]) * 100
    
    return report


def main():
    parser = argparse.ArgumentParser(description="Archive old media files from Memex")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be archived without actually archiving"
    )
    parser.add_argument(
        "--age-days",
        type=int,
        default=ARCHIVE_AGE_DAYS,
        help=f"Archive files older than this many days (default: {ARCHIVE_AGE_DAYS})"
    )
    parser.add_argument(
        "--archive-root",
        type=Path,
        default=ARCHIVE_ROOT,
        help=f"Root directory for archives (default: {ARCHIVE_ROOT})"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("Memex Media Archival System")
    logger.info("=" * 60)
    logger.info(f"Archive age threshold: {args.age_days} days")
    logger.info(f"Archive root: {args.archive_root}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("")
    
    all_results = []
    
    for media_dir in MEDIA_DIRS:
        results = archive_media_directory(
            media_dir,
            args.archive_root,
            args.age_days,
            dry_run=args.dry_run
        )
        all_results.extend(results)
    
    # Generate and log report
    report = generate_archive_report(all_results)
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("Archive Report")
    logger.info("=" * 60)
    logger.info(json.dumps(report, indent=2))
    
    # Save report to file
    report_path = args.archive_root / "reports" / f"archive_report_{int(time.time())}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, 'w') as f:
        json.dump({"report": report, "details": all_results}, f, indent=2)
    
    logger.info(f"Report saved: {report_path}")
    
    if args.dry_run:
        logger.info("")
        logger.info("DRY RUN - No files were actually archived")
    
    return 0 if report["errors"] == 0 else 1


if __name__ == "__main__":
    exit(main())
