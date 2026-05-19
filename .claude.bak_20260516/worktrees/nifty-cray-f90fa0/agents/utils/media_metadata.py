"""
Media metadata extraction utilities for chat integration.
Converts generated media files into structured metadata for chat preview/download.
"""

import os
import uuid
import mimetypes
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger("MediaMetadata")

# Media types that can be previewed in browser
PREVIEWABLE_IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
PREVIEWABLE_VIDEO_TYPES = {"video/mp4", "video/webm"}
PREVIEWABLE_AUDIO_TYPES = {"audio/mp3", "audio/mpeg", "audio/wav", "audio/ogg"}
PREVIEWABLE_MODEL_TYPES = {"model/gltf-binary", "model/gltf+json"}


def extract_media_metadata(
    filename: str,
    base_path: str = "/workspace/delivered_artifacts",
    url_prefix: str = "/api/backend/v1/art/files",
) -> Optional[Dict]:
    """
    Extract structured metadata for a generated media file.
    
    Args:
        filename: Name of the generated file (e.g., "image_123.png")
        base_path: Directory where the file is stored
        url_prefix: URL prefix for serving the file
    
    Returns:
        Dict with media metadata or None if file doesn't exist
    """
    file_path = Path(base_path) / filename
    
    if not file_path.exists():
        logger.warning(f"Media file not found: {file_path}")
        return None
    
    # Get file stats
    stat = file_path.stat()
    size = stat.st_size
    
    # Determine MIME type
    mime_type, _ = mimetypes.guess_type(str(file_path))
    if not mime_type:
        # Fallback for common extensions
        ext = file_path.suffix.lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".mp4": "video/mp4",
            ".webm": "video/webm",
            ".mp3": "audio/mpeg",
            ".wav": "audio/wav",
            ".ogg": "audio/ogg",
            ".glb": "model/gltf-binary",
            ".gltf": "model/gltf+json",
            ".obj": "model/obj",
            ".stl": "model/stl",
        }
        mime_type = mime_map.get(ext, "application/octet-stream")
    
    # Check if previewable
    previewable = (
        mime_type in PREVIEWABLE_IMAGE_TYPES
        or mime_type in PREVIEWABLE_VIDEO_TYPES
        or mime_type in PREVIEWABLE_AUDIO_TYPES
        or mime_type in PREVIEWABLE_MODEL_TYPES
    )
    
    # Extract dimensions for images
    width, height = None, None
    if mime_type in PREVIEWABLE_IMAGE_TYPES:
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                width, height = img.size
        except Exception as e:
            logger.debug(f"Could not extract image dimensions: {e}")
    
    # Build metadata
    media_id = str(uuid.uuid4())
    return {
        "id": media_id,
        "filename": filename,
        "mimeType": mime_type,
        "url": f"{url_prefix}/{filename}?dl=0",  # Inline/preview
        "downloadUrl": f"{url_prefix}/{filename}?dl=1",  # Force download
        "size": size,
        "width": width,
        "height": height,
        "previewable": previewable,
    }


def parse_generated_media(result_text: str) -> Optional[Dict]:
    """
    Parse a generation result string to extract media metadata.
    
    Handles patterns like:
    - "Generated Image: filename.png (Saved to Gallery) | ✅ Verified."
    - "Generated 3D Model: model.glb | Ready for download"
    
    Returns:
        Media metadata dict or None if no media found
    """
    import re
    
    # Pattern 1: Image generation
    img_match = re.search(r"Generated Image:\s*([\w.\-]+)", result_text)
    if img_match:
        filename = img_match.group(1)
        return extract_media_metadata(filename)
    
    # Pattern 2: 3D model generation
    model_match = re.search(r"Generated (?:3D Model|Model):\s*([\w.\-]+)", result_text)
    if model_match:
        filename = model_match.group(1)
        return extract_media_metadata(
            filename,
            base_path="/app/comfy_io/output",
            url_prefix="/api/backend/v1/art/files",
        )
    
    # Pattern 3: Direct file path reference
    path_match = re.search(r"(/[^\s]+\.(?:glb|obj|stl|png|jpg|jpeg|webp|mp4|webm))", result_text, re.IGNORECASE)
    if path_match:
        full_path = path_match.group(1)
        filename = os.path.basename(full_path)
        base_path = os.path.dirname(full_path)
        return extract_media_metadata(
            filename,
            base_path=base_path,
            url_prefix="/api/backend/v1/art/files",
        )
    
    return None
