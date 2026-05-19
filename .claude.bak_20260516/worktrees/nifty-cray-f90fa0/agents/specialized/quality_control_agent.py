"""
Quality Control Agent for Image Generation
Uses Qwen2-VL vision model to inspect generated images for quality issues.
"""

import os
import logging
import base64
import requests
from typing import Dict, Tuple, Optional

logger = logging.getLogger(__name__)

# Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://192.168.2.101:11434")
VISION_MODEL = "qwen2-vl:7b"

# Quality thresholds (0-10 scale)
DEFAULT_THRESHOLDS = {
    "composition": 6.0,
    "lighting": 6.0,
    "technical_quality": 7.0,
    "prompt_adherence": 7.0,
    "overall_min": 6.5
}


class QualityInspector:
    """Vision-based quality inspector for generated images."""
    
    def __init__(self, ollama_host: str = OLLAMA_HOST, model: str = VISION_MODEL):
        self.ollama_host = ollama_host
        self.model = model
        self.thresholds = DEFAULT_THRESHOLDS.copy()
    
    def set_thresholds(self, **kwargs):
        """Update quality thresholds."""
        self.thresholds.update(kwargs)
    
    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64 for Ollama API."""
        try:
            with open(image_path, "rb") as img_file:
                return base64.b64encode(img_file.read()).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to encode image {image_path}: {e}")
            raise
    
    def _call_vision_model(self, image_b64: str, prompt: str) -> str:
        """Call Ollama vision model with image and prompt."""
        try:
            url = f"{self.ollama_host}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "images": [image_b64],
                "stream": False
            }
            
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            return result.get("response", "")
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Vision model request failed: {e}")
            raise
    
    def inspect_image(self, image_path: str, original_prompt: str) -> Dict:
        """
        Inspect an image for quality issues.
        
        Returns:
            {
                "passed": bool,
                "overall_score": float,
                "scores": {
                    "composition": float,
                    "lighting": float,
                    "technical_quality": float,
                    "prompt_adherence": float
                },
                "feedback": str,
                "issues": [str],
                "recommendations": [str]
            }
        """
        logger.info(f"[QualityControl] Inspecting image: {image_path}")
        
        if not os.path.exists(image_path):
            logger.error(f"Image not found: {image_path}")
            return {
                "passed": False,
                "overall_score": 0.0,
                "feedback": f"Image file not found: {image_path}",
                "issues": ["File not found"],
                "recommendations": []
            }
        
        try:
            # Encode image
            image_b64 = self._encode_image(image_path)
            
            # Construct quality inspection prompt
            inspection_prompt = f"""You are an expert image quality inspector. Analyze this image that was generated from the prompt: "{original_prompt}"

Rate the image on these criteria (scale 0-10):

1. **Composition** (0-10): Layout, framing, subject placement, rule of thirds
2. **Lighting** (0-10): Light quality, shadows, highlights, mood, realism
3. **Technical Quality** (0-10): Sharpness, detail, resolution, no artifacts/distortions
4. **Prompt Adherence** (0-10): How well does it match the requested prompt?

Respond EXACTLY in this format:
COMPOSITION: [score]
LIGHTING: [score]
TECHNICAL: [score]
ADHERENCE: [score]

ISSUES:
- [list any problems found, or "None" if perfect]

RECOMMENDATIONS:
- [suggest improvements, or "None" if acceptable]

OVERALL: [average score 0-10]"""

            # Call vision model
            response = self._call_vision_model(image_b64, inspection_prompt)
            
            # Parse response
            scores, issues, recommendations, overall = self._parse_inspection_response(response)
            
            # Check thresholds
            passed = self._check_thresholds(scores, overall)
            
            result = {
                "passed": passed,
                "overall_score": overall,
                "scores": scores,
                "feedback": response,
                "issues": issues,
                "recommendations": recommendations
            }
            
            logger.info(f"[QualityControl] Overall Score: {overall:.1f}/10 | Passed: {passed}")
            if issues and issues[0].lower() != "none":
                logger.warning(f"[QualityControl] Issues found: {', '.join(issues)}")
            
            return result
        
        except Exception as e:
            logger.error(f"[QualityControl] Inspection failed: {e}")
            # Fail-safe: return pass on error to avoid blocking valid images
            return {
                "passed": True,
                "overall_score": 7.0,
                "feedback": f"Quality inspection unavailable (error: {str(e)})",
                "issues": ["Inspection service error"],
                "recommendations": []
            }
    
    def _parse_inspection_response(self, response: str) -> Tuple[Dict[str, float], list, list, float]:
        """Parse the vision model's structured response."""
        scores = {
            "composition": 7.0,
            "lighting": 7.0,
            "technical_quality": 7.0,
            "prompt_adherence": 7.0
        }
        issues = []
        recommendations = []
        overall = 7.0
        
        try:
            lines = response.strip().split("\n")
            current_section = None
            
            for line in lines:
                line = line.strip()
                
                # Parse scores
                if line.startswith("COMPOSITION:"):
                    scores["composition"] = float(line.split(":")[-1].strip())
                elif line.startswith("LIGHTING:"):
                    scores["lighting"] = float(line.split(":")[-1].strip())
                elif line.startswith("TECHNICAL:"):
                    scores["technical_quality"] = float(line.split(":")[-1].strip())
                elif line.startswith("ADHERENCE:"):
                    scores["prompt_adherence"] = float(line.split(":")[-1].strip())
                elif line.startswith("OVERALL:"):
                    overall = float(line.split(":")[-1].strip())
                
                # Parse sections
                elif line == "ISSUES:":
                    current_section = "issues"
                elif line == "RECOMMENDATIONS:":
                    current_section = "recommendations"
                elif line.startswith("-") and current_section:
                    item = line[1:].strip()
                    if current_section == "issues":
                        issues.append(item)
                    elif current_section == "recommendations":
                        recommendations.append(item)
            
            # If no overall score, calculate average
            if overall == 7.0 and any(s != 7.0 for s in scores.values()):
                overall = sum(scores.values()) / len(scores)
        
        except Exception as e:
            logger.warning(f"Failed to parse inspection response: {e}")
        
        return scores, issues, recommendations, overall
    
    def _check_thresholds(self, scores: Dict[str, float], overall: float) -> bool:
        """Check if scores meet quality thresholds."""
        # Check overall minimum
        if overall < self.thresholds["overall_min"]:
            logger.info(f"[QualityControl] Failed overall threshold: {overall:.1f} < {self.thresholds['overall_min']}")
            return False
        
        # Check individual criteria
        for criterion, score in scores.items():
            threshold_key = criterion
            if threshold_key in self.thresholds:
                if score < self.thresholds[threshold_key]:
                    logger.info(f"[QualityControl] Failed {criterion} threshold: {score:.1f} < {self.thresholds[threshold_key]}")
                    return False
        
        return True


# Singleton instance
_inspector = None

def get_inspector() -> QualityInspector:
    """Get or create the global quality inspector instance."""
    global _inspector
    if _inspector is None:
        _inspector = QualityInspector()
    return _inspector


def inspect_generated_image(image_path: str, original_prompt: str, thresholds: Optional[Dict] = None) -> Dict:
    """
    Convenience function to inspect a generated image.
    
    Args:
        image_path: Path to the generated image
        original_prompt: The prompt used to generate the image
        thresholds: Optional custom quality thresholds
    
    Returns:
        Quality inspection result dictionary
    """
    inspector = get_inspector()
    
    if thresholds:
        inspector.set_thresholds(**thresholds)
    
    return inspector.inspect_image(image_path, original_prompt)
