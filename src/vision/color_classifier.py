"""
Color-Histogram Based Disease Classifier.

Fallback classifier that analyzes pixel color distributions to detect
plant disease patterns when CNN model is untrained or unreliable.
Uses HSV color space segmentation + disease severity scoring.
"""

import os
import sys
import numpy as np
from typing import Dict, Tuple, Optional
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


DISEASE_PROFILES = {
    "tomato_early_blight": {
        "plant": "Tomato", "disease": "Early blight",
        "brown_min": 0.03, "yellow_min": 0.02, "dark_max": 0.15,
        "green_max": 0.75, "priority": 1
    },
    "tomato_late_blight": {
        "plant": "Tomato", "disease": "Late blight",
        "brown_min": 0.04, "yellow_min": 0.01, "dark_min": 0.03,
        "green_max": 0.70, "priority": 2
    },
    "potato_early_blight": {
        "plant": "Potato", "disease": "Early blight",
        "brown_min": 0.03, "yellow_min": 0.02, "dark_max": 0.15,
        "green_max": 0.75, "priority": 1
    },
    "potato_late_blight": {
        "plant": "Potato", "disease": "Late blight",
        "brown_min": 0.04, "yellow_min": 0.01, "dark_min": 0.03,
        "green_max": 0.70, "priority": 2
    },
    "tomato_bacterial_spot": {
        "plant": "Tomato", "disease": "Bacterial spot",
        "brown_min": 0.02, "dark_min": 0.02, "yellow_min": 0.01,
        "green_max": 0.80, "priority": 3
    },
    "tomato_septoria_leaf_spot": {
        "plant": "Tomato", "disease": "Septoria leaf spot",
        "brown_min": 0.03, "dark_min": 0.01, "yellow_min": 0.03,
        "green_max": 0.75, "priority": 3
    },
    "tomato_leaf_mold": {
        "plant": "Tomato", "disease": "Leaf Mold",
        "yellow_min": 0.05, "brown_min": 0.01, "green_max": 0.70,
        "priority": 4
    },
    "tomato_target_spot": {
        "plant": "Tomato", "disease": "Target Spot",
        "brown_min": 0.04, "yellow_min": 0.03, "green_max": 0.70,
        "priority": 3
    },
    "tomato_yellow_leaf_curl_virus": {
        "plant": "Tomato", "disease": "Tomato Yellow Leaf Curl Virus",
        "yellow_min": 0.10, "green_max": 0.60, "brown_min": 0.00,
        "priority": 2
    },
    "tomato_spider_mites": {
        "plant": "Tomato", "disease": "Two-spotted spider mite",
        "yellow_min": 0.06, "brown_min": 0.02, "green_max": 0.65,
        "priority": 4
    },
    "tomato_healthy": {
        "plant": "Tomato", "disease": "Healthy",
        "green_min": 0.45, "brown_max": 0.02, "yellow_max": 0.02,
        "priority": 99
    },
    "bell_pepper_bacterial_spot": {
        "plant": "Bell Pepper", "disease": "Bacterial spot",
        "brown_min": 0.02, "dark_min": 0.02, "yellow_min": 0.01,
        "green_max": 0.80, "priority": 3
    },
    "bell_pepper_healthy": {
        "plant": "Bell Pepper", "disease": "Healthy",
        "green_min": 0.45, "brown_max": 0.02, "yellow_max": 0.02,
        "priority": 99
    },
    "apple_apple_scab": {
        "plant": "Apple", "disease": "Apple scab",
        "brown_min": 0.03, "dark_min": 0.01, "green_max": 0.75,
        "priority": 3
    },
    "apple_black_rot": {
        "plant": "Apple", "disease": "Black rot",
        "brown_min": 0.04, "dark_min": 0.02, "green_max": 0.70,
        "priority": 3
    },
    "apple_cedar_apple_rust": {
        "plant": "Apple", "disease": "Cedar apple rust",
        "yellow_min": 0.05, "brown_min": 0.02, "green_max": 0.70,
        "priority": 3
    },
    "apple_healthy": {
        "plant": "Apple", "disease": "Healthy",
        "green_min": 0.45, "brown_max": 0.02, "yellow_max": 0.02,
        "priority": 99
    },
    "grape_black_rot": {
        "plant": "Grape", "disease": "Black rot",
        "brown_min": 0.04, "dark_min": 0.02, "green_max": 0.70,
        "priority": 3
    },
    "grape_healthy": {
        "plant": "Grape", "disease": "Healthy",
        "green_min": 0.45, "brown_max": 0.02, "yellow_max": 0.02,
        "priority": 99
    },
    "corn_common_rust": {
        "plant": "Corn (maize)", "disease": "Common rust",
        "brown_min": 0.03, "yellow_min": 0.02, "green_max": 0.75,
        "priority": 3
    },
    "corn_northern_leaf_blight": {
        "plant": "Corn (maize)", "disease": "Northern Leaf Blight",
        "brown_min": 0.04, "dark_min": 0.01, "green_max": 0.70,
        "priority": 3
    },
    "corn_healthy": {
        "plant": "Corn (maize)", "disease": "Healthy",
        "green_min": 0.45, "brown_max": 0.02, "yellow_max": 0.02,
        "priority": 99
    },
    "potato_healthy": {
        "plant": "Potato", "disease": "Healthy",
        "green_min": 0.45, "brown_max": 0.02, "yellow_max": 0.02,
        "priority": 99
    },
    "strawberry_leaf_scorch": {
        "plant": "Strawberry", "disease": "Leaf scorch",
        "brown_min": 0.05, "yellow_min": 0.03, "green_max": 0.65,
        "priority": 3
    },
    "strawberry_healthy": {
        "plant": "Strawberry", "disease": "Healthy",
        "green_min": 0.45, "brown_max": 0.02, "yellow_max": 0.02,
        "priority": 99
    },
}


def analyze_colors(image) -> Dict[str, float]:
    """Analyze pixel color distribution of an image."""
    if isinstance(image, str):
        img = Image.open(image).convert("RGB")
        img = img.resize((128, 128))
        arr = np.array(img, dtype=np.float32)
    elif isinstance(image, Image.Image):
        img = image.convert("RGB").resize((128, 128))
        arr = np.array(img, dtype=np.float32)
    elif isinstance(image, np.ndarray):
        if image.ndim == 3 and image.shape[2] == 3:
            if image.dtype != np.float32:
                img = Image.fromarray(image.astype(np.uint8)).resize((128, 128))
                arr = np.array(img, dtype=np.float32)
            else:
                arr = image
        else:
            return {"brown": 0, "yellow": 0, "green": 0, "dark": 0, "total": 1}
    else:
        return {"brown": 0, "yellow": 0, "green": 0, "dark": 0, "total": 1}

    r = arr[:, :, 0]
    g = arr[:, :, 1]
    b = arr[:, :, 2]
    total = r.size

    brown_mask = (r > 60) & (r < 200) & (g > 30) & (g < 150) & (b < 110) & (r > g * 1.02)
    yellow_mask = (r > 130) & (g > 120) & (b < 120) & (np.abs(r - g) < 60) & (g > b * 1.2)
    green_mask = (g > 50) & (g > r * 1.08) & (g > b * 1.08)
    dark_mask = (r < 65) & (g < 65) & (b < 65)

    return {
        "brown": float(np.sum(brown_mask)) / total,
        "yellow": float(np.sum(yellow_mask)) / total,
        "green": float(np.sum(green_mask)) / total,
        "dark": float(np.sum(dark_mask)) / total,
        "total": total
    }


def classify_by_color(image, plant_hint: str = "") -> Dict:
    """
    Classify disease from color analysis.

    Returns: {canonical_id, plant, disease, confidence, status}
    """
    ratios = analyze_colors(image)
    brown = ratios["brown"]
    yellow = ratios["yellow"]
    green = ratios["green"]
    dark = ratios["dark"]

    fn = plant_hint.lower()

    candidates = []

    for cid, profile in DISEASE_PROFILES.items():
        score = 0.0
        checks_passed = 0
        total_checks = 0

        if "green_min" in profile:
            total_checks += 1
            if green >= profile["green_min"]:
                score += 1.0
                checks_passed += 1
            else:
                score -= 0.3

        if "brown_min" in profile:
            total_checks += 1
            if brown >= profile["brown_min"]:
                score += 1.5
                checks_passed += 1

        if "brown_max" in profile:
            total_checks += 1
            if brown <= profile["brown_max"]:
                score += 1.0
                checks_passed += 1

        if "yellow_min" in profile:
            total_checks += 1
            if yellow >= profile["yellow_min"]:
                score += 1.2
                checks_passed += 1

        if "yellow_max" in profile:
            total_checks += 1
            if yellow <= profile["yellow_max"]:
                score += 1.0
                checks_passed += 1

        if "dark_min" in profile:
            total_checks += 1
            if dark >= profile["dark_min"]:
                score += 1.0
                checks_passed += 1

        if "dark_max" in profile:
            total_checks += 1
            if dark <= profile["dark_max"]:
                score += 0.5
                checks_passed += 1

        if "green_max" in profile:
            total_checks += 1
            if green <= profile["green_max"]:
                score += 0.8
                checks_passed += 1

        if plant_hint:
            if fn in cid or cid.split("_")[0] in fn:
                score += 2.0

        if total_checks > 0:
            match_ratio = checks_passed / total_checks
            final_score = score * match_ratio * (1.0 + profile.get("priority", 5) * 0.05)
            candidates.append((cid, final_score, match_ratio))

    candidates.sort(key=lambda x: x[1], reverse=True)

    if not candidates:
        return {
            "canonical_id": "tomato_healthy",
            "plant": "Tomato",
            "disease": "Healthy",
            "confidence": 0.50,
            "status": "uncertain"
        }

    best_cid, best_score, best_match = candidates[0]
    second_score = candidates[1][1] if len(candidates) > 1 else 0

    confidence = min(0.97, 0.55 + best_match * 0.30 + (best_score - second_score) * 0.05)
    confidence = max(0.50, confidence)

    is_healthy = DISEASE_PROFILES.get(best_cid, {}).get("priority", 0) == 99
    has_lesions = brown > 0.02 or yellow > 0.03 or dark > 0.02

    if is_healthy and has_lesions:
        for cid, score, match in candidates:
            if DISEASE_PROFILES.get(cid, {}).get("priority", 99) < 99:
                best_cid = cid
                confidence = max(0.65, confidence - 0.1)
                break

    profile = DISEASE_PROFILES.get(best_cid, {})
    status = "supported" if confidence >= 0.55 else "uncertain"

    return {
        "canonical_id": best_cid,
        "plant": profile.get("plant", "Tomato"),
        "disease": profile.get("disease", "Unknown"),
        "confidence": round(confidence, 4),
        "status": status
    }
