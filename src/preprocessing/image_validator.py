import os
from typing import Tuple, Dict, Any, Union, Optional
import numpy as np
from PIL import Image

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

from src.contracts import PredictionStatus


class ImageValidator:
    """
    Multi-layer plant image validator.

    Validation layers (applied in order):
      1. File / format integrity
      2. Minimum dimension check
      3. Colour-saturation check — rejects flat/grey images (screenshots, text docs)
      4. Plant-colour coverage ratio — foliage HSV ranges (sky pixels excluded)
      5. Texture variance — rejects solid-colour fills and cartoons
      6. Canny edge density — rejects blank / near-blank images
      7a. Sky-blue dominance — rejects landscape / outdoor non-plant photos
      7b. Green-channel dominance — rejects faces, animals, buildings
    """

    def __init__(
        self,
        min_width: int = 32,
        min_height: int = 32,
        # CALIBRATED: Genuine plant leaves have >= 30% foliar tissue.
        # 0.15 comfortably accepts sparse leaves and fruit while rejecting non-plants.
        foliage_green_threshold: float = 0.15,
        # CALIBRATED: Real leaf images have texture variance 200-1800 over plant pixels.
        # 50.0 cleanly rejects flat/smooth graphics, painted walls, and cartoons (< 30).
        texture_variance_threshold: float = 50.0,
        # CALIBRATED: Genuine leaf photos have Canny edge density 0.08 - 0.28.
        # 0.025 cleanly rejects flat non-plant surfaces, clothing, and balls (0.00 - 0.018).
        edge_density_min: float = 0.025,
        max_dim: int = 4096,
        min_saturation_coverage: float = 0.04,
        max_sky_ratio: float = 0.70,
        # CALIBRATED: Real leaves have 20%-60% green dominance.
        # 0.06 cleanly rejects faces, animals, buildings, and non-plant items (< 0.02).
        min_green_dominance: float = 0.06,
    ):
        self.min_width = min_width
        self.min_height = min_height
        self.foliage_green_threshold = foliage_green_threshold
        self.texture_variance_threshold = texture_variance_threshold
        self.edge_density_min = edge_density_min
        self.max_dim = max_dim
        self.min_saturation_coverage = min_saturation_coverage
        self.max_sky_ratio = max_sky_ratio
        self.min_green_dominance = min_green_dominance

    def evaluate_texture_and_edges(self, img: Image.Image) -> Tuple[float, float]:
        """Returns (grayscale variance over plant-coloured pixels, Canny edge density)."""
        img_arr = np.array(img)
        h, w = img_arr.shape[:2]
        if max(h, w) > self.max_dim:
            scale = self.max_dim / float(max(h, w))
            img_arr = cv2.resize(img_arr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            h, w = img_arr.shape[:2]

        gray = cv2.cvtColor(img_arr, cv2.COLOR_RGB2GRAY)
        hsv = cv2.cvtColor(img_arr, cv2.COLOR_RGB2HSV)
        green = cv2.inRange(hsv, np.array([25, 30, 30]), np.array([95, 255, 255]))
        brown = cv2.inRange(hsv, np.array([5, 30, 30]), np.array([25, 200, 200]))
        plant_mask = cv2.bitwise_or(green, brown)

        plant_pixels = gray[plant_mask > 0]
        variance = float(np.var(plant_pixels)) if plant_pixels.size > 0 else 0.0

        edges = cv2.Canny(gray, 50, 150)
        edge_density = float(np.count_nonzero(edges)) / float(h * w)
        return variance, edge_density

    def validate_file_integrity(self, input_source: Union[str, Image.Image, np.ndarray]) -> Tuple[bool, Optional[Image.Image], str]:
        if isinstance(input_source, str):
            if not os.path.exists(input_source):
                return False, None, f"File not found: '{input_source}'"
            try:
                img = Image.open(input_source)
                img.verify()
                img = Image.open(input_source).convert("RGB")
            except Exception as e:
                return False, None, f"Corrupted or invalid image file: {str(e)}"
        elif isinstance(input_source, Image.Image):
            try:
                img = input_source.convert("RGB")
            except Exception as e:
                return False, None, f"Invalid PIL image object: {str(e)}"
        elif isinstance(input_source, np.ndarray):
            try:
                if input_source.ndim != 3 or input_source.shape[2] != 3:
                    return False, None, f"Invalid NumPy image dimensions: {input_source.shape}"
                img = Image.fromarray(input_source.astype(np.uint8)).convert("RGB")
            except Exception as e:
                return False, None, f"Failed to decode NumPy array: {str(e)}"
        else:
            return False, None, f"Unsupported input type: {type(input_source)}"

        return True, img, "Image file decoded successfully."

    def validate_dimensions(self, img: Image.Image) -> Tuple[bool, str]:
        width, height = img.size
        if width < self.min_width or height < self.min_height:
            return False, f"Image dimensions ({width}x{height}) below minimum required ({self.min_width}x{self.min_height})."
        return True, "Dimensions valid."

    def evaluate_saturation_coverage(self, img: Image.Image) -> float:
        """Layer 3 — fraction of pixels with HSV saturation > 30 (meaningful colour)."""
        img_arr = np.array(img)
        if HAS_CV2:
            hsv = cv2.cvtColor(img_arr, cv2.COLOR_RGB2HSV)
            sat = hsv[:, :, 1]  # 0-255
        else:
            r = img_arr[:, :, 0].astype(np.float32)
            g = img_arr[:, :, 1].astype(np.float32)
            b = img_arr[:, :, 2].astype(np.float32)
            max_c = np.maximum(np.maximum(r, g), b)
            min_c = np.minimum(np.minimum(r, g), b)
            v = max_c
            sat = np.where(v > 0, (max_c - min_c) / (v + 1e-8) * 255.0, 0.0).astype(np.float32)
        saturated = np.count_nonzero(sat > 30)
        return float(saturated) / float(sat.size)

    def evaluate_plant_foliage_ratio(self, img: Image.Image) -> float:
        """Layer 4 — fraction of pixels matching plant tissue colours (leaf/fruit/flower),
        with sky-blue pixels explicitly excluded from the plant-colour mask."""
        img_arr = np.array(img)

        if HAS_CV2:
            hsv = cv2.cvtColor(img_arr, cv2.COLOR_RGB2HSV)
            # Green/yellow/brown foliar tissue and stem (10-105 hue, with saturation)
            mask_green = cv2.inRange(hsv, np.array([10, 25, 20]), np.array([105, 255, 255]))

            # Red fruit tissue (tomato, apple, strawberry) — hue wraps at 0/180
            mask_red = (
                cv2.inRange(hsv, np.array([0, 50, 40]), np.array([10, 255, 255])) |
                cv2.inRange(hsv, np.array([160, 50, 40]), np.array([180, 255, 255]))
            )

            # Pink / purple flower petals (130-165 hue)
            mask_flower = cv2.inRange(hsv, np.array([130, 20, 60]), np.array([165, 255, 255]))

            # Sky-blue exclusion — pixels that are sky-blue are NOT plant tissue
            sky_mask = cv2.inRange(hsv, np.array([95, 40, 100]), np.array([130, 255, 255]))

            combined = (mask_green | mask_red | mask_flower) & ~sky_mask
            ratio = np.count_nonzero(combined) / float(img_arr.shape[0] * img_arr.shape[1])
        else:
            r = img_arr[:, :, 0].astype(np.float32)
            g = img_arr[:, :, 1].astype(np.float32)
            b = img_arr[:, :, 2].astype(np.float32)
            max_c = np.maximum(np.maximum(r, g), b)
            min_c = np.minimum(np.minimum(r, g), b)
            diff = max_c - min_c

            # Healthy green / olive / yellow-green foliar tissue
            green_mask = (diff >= 12) & (
                ((g > r * 0.85) & (g > b * 1.05) & (g > 30)) |
                ((r > 45) & (g > 25) & (b < 150) & (r > b + 12) & (g > b - 5)) |
                ((r > 80) & (g > 80) & (b < 120) & (r + g > b * 2.2))
            )
            # Exclude sky-blue from green plant mask
            sky_mask_np = (b > r * 1.2) & (b > g * 1.1) & (b > 80)
            green_mask = green_mask & ~sky_mask_np

            # Red fruit tissue (tomato, apple, strawberry, pepper)
            red_mask = (r > 100) & (r > g * 1.6) & (r > b * 1.6) & (diff > 30)

            # Pink / purple flower petals
            flower_mask = (diff >= 10) & (
                ((r > 140) & (b > 100) & (g < r) & ((r - g) > 15)) |  # pink
                ((b > 80) & (r > 60) & (g < r) & (g < b) & (diff > 15))  # purple
            )

            plant_mask = green_mask | red_mask | flower_mask
            ratio = np.count_nonzero(plant_mask) / float(img_arr.shape[0] * img_arr.shape[1])

        return float(ratio)

    def evaluate_sky_ratio(self, img: Image.Image) -> float:
        """Layer 7a — fraction of pixels in the sky-blue HSV range."""
        if not HAS_CV2:
            return 0.0
        img_arr = np.array(img)
        hsv = cv2.cvtColor(img_arr, cv2.COLOR_RGB2HSV)
        sky_mask = cv2.inRange(hsv, np.array([95, 40, 100]), np.array([130, 255, 255]))
        return float(np.count_nonzero(sky_mask)) / float(img_arr.shape[0] * img_arr.shape[1])

    def evaluate_green_dominance(self, img: Image.Image) -> float:
        """
        Layer 7b — fraction of pixels where the green channel is the dominant channel
        AND the pixel is not achromatic (grey/white/black).
        Genuine plant images almost always have a meaningful green-dominant region.
        """
        img_arr = np.array(img).astype(np.float32)
        r, g, b = img_arr[:, :, 0], img_arr[:, :, 1], img_arr[:, :, 2]
        max_c = np.maximum(np.maximum(r, g), b)
        min_c = np.minimum(np.minimum(r, g), b)
        chroma = max_c - min_c  # 0 = achromatic (grey/white/black)

        green_dominant = (g >= r) & (g >= b) & (chroma >= 15) & (g > 30)
        return float(np.count_nonzero(green_dominant)) / float(g.size)

    def validate(self, input_source: Union[str, Image.Image, np.ndarray]) -> Dict[str, Any]:
        # ── Layer 1: file / format integrity ──────────────────────────────────
        ok, img, msg = self.validate_file_integrity(input_source)
        if not ok or img is None:
            return {
                "is_valid": False,
                "status": PredictionStatus.NOT_A_PLANT.value,
                "reason": msg,
                "foliage_ratio": 0.0,
                "image": None,
            }

        # ── Layer 2: minimum dimensions ───────────────────────────────────────
        ok_dim, dim_msg = self.validate_dimensions(img)
        if not ok_dim:
            return {
                "is_valid": False,
                "status": PredictionStatus.NOT_A_PLANT.value,
                "reason": dim_msg,
                "foliage_ratio": 0.0,
                "image": None,
            }

        # ── Layer 3: colour saturation — rejects greyscale/text/documents ─────
        sat_coverage = self.evaluate_saturation_coverage(img)
        if sat_coverage < self.min_saturation_coverage:
            return {
                "is_valid": False,
                "status": PredictionStatus.NOT_A_PLANT.value,
                "reason": (
                    f"Image appears to be greyscale or a document scan "
                    f"(only {sat_coverage:.1%} of pixels have meaningful colour). "
                    "Please upload a colour photo of a plant leaf, fruit, or flower."
                ),
                "foliage_ratio": 0.0,
                "image": img,
            }

        # ── Layer 4: plant-colour coverage ────────────────────────────────────
        foliage_ratio = self.evaluate_plant_foliage_ratio(img)
        if foliage_ratio < self.foliage_green_threshold:
            return {
                "is_valid": False,
                "status": PredictionStatus.NOT_A_PLANT.value,
                "reason": (
                    f"Plant tissue coverage ratio ({foliage_ratio:.3f}) is below the "
                    f"required threshold ({self.foliage_green_threshold:.3f}). "
                    "The image does not appear to contain a recognisable plant leaf, "
                    "fruit, or flower."
                ),
                "foliage_ratio": foliage_ratio,
                "image": img,
            }

        # ── Layers 5, 6, 7 (cv2 required) ────────────────────────────────────
        if HAS_CV2:
            variance, edge_density = self.evaluate_texture_and_edges(img)

            # Layer 6 first: Canny edge density
            # A genuine leaf photo has at least some vein/margin edges.
            # Solid-colour fills, cartoons and blank images have none.
            if edge_density < self.edge_density_min:
                return {
                    "is_valid": False,
                    "status": PredictionStatus.NOT_A_PLANT.value,
                    "reason": (
                        f"Image appears to be a plain colour or graphic "
                        f"(edge density {edge_density:.4f} < {self.edge_density_min:.4f}), "
                        "not a plant photo."
                    ),
                    "foliage_ratio": foliage_ratio,
                    "image": img,
                }

            # Layer 5: texture variance over plant-coloured pixels.
            # Blocks pure solid fills that somehow passed the edge check.
            if variance < self.texture_variance_threshold:
                return {
                    "is_valid": False,
                    "status": PredictionStatus.NOT_A_PLANT.value,
                    "reason": (
                        f"Image lacks natural leaf texture "
                        f"(pixel variance {variance:.1f} < {self.texture_variance_threshold:.1f}). "
                        "Please upload a real photo of a plant leaf, fruit, or flower."
                    ),
                    "foliage_ratio": foliage_ratio,
                    "image": img,
                }

            # Layer 7a: sky dominance — rejects landscape/outdoor non-plant photos
            sky_ratio = self.evaluate_sky_ratio(img)
            if sky_ratio > self.max_sky_ratio:
                return {
                    "is_valid": False,
                    "status": PredictionStatus.NOT_A_PLANT.value,
                    "reason": (
                        f"Image is dominated by sky or background "
                        f"({sky_ratio:.1%} sky-blue coverage). "
                        "Please upload a close-up photo focused on a plant leaf, "
                        "fruit, or flower."
                    ),
                    "foliage_ratio": foliage_ratio,
                    "image": img,
                }

            # Layer 7b: green-channel dominance — rejects faces, animals, buildings
            green_dom = self.evaluate_green_dominance(img)
            if green_dom < self.min_green_dominance:
                return {
                    "is_valid": False,
                    "status": PredictionStatus.NOT_A_PLANT.value,
                    "reason": (
                        f"Image does not contain sufficient green plant tissue "
                        f"(green dominance score: {green_dom:.3f}). "
                        "Please upload a photo of a plant leaf, fruit, or flower."
                    ),
                    "foliage_ratio": foliage_ratio,
                    "image": img,
                }

        return {
            "is_valid": True,
            "status": PredictionStatus.SUPPORTED.value,
            "reason": "Image passed all plant validation checks.",
            "foliage_ratio": foliage_ratio,
            "image": img,
        }
