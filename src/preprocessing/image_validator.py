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
      7b. Human detection — rejects portraits and full-body people before inference
    """

    def __init__(
        self,
        min_width: int = 32,
        min_height: int = 32,
        # Require visible green/yellow foliage; colored objects and fruit alone do not qualify as leaf images.
        foliage_green_threshold: float = 0.08,
        # CALIBRATED: Pure flat graphics / blank fills have variance < 2.0; genuine leaves have >= 10.0
        texture_variance_threshold: float = 4.0,
        # CALIBRATED: Edge density floor applied in conjunction with variance floor to reject solid fills
        edge_density_min: float = 0.0005,
        max_dim: int = 4096,
        min_saturation_coverage: float = 0.03,
        max_sky_ratio: float = 0.75,
        # CALIBRATED: Diseased/blighted brown/yellow leaves often have low green-dominance; handled by foliage ratio
        min_green_dominance: float = 0.0,
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
        self._face_cascade = None
        self._people_hog = None
        if HAS_CV2:
            try:
                cascade_path = os.path.join(cv2.data.haarcascades, "haarcascade_frontalface_default.xml")
                cascade = cv2.CascadeClassifier(cascade_path)
                if not cascade.empty():
                    self._face_cascade = cascade
            except (AttributeError, cv2.error, OSError):
                # Keep validation usable in minimal OpenCV installations.
                self._face_cascade = None
            try:
                people_hog = cv2.HOGDescriptor()
                people_hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
                self._people_hog = people_hog
            except (AttributeError, cv2.error):
                self._people_hog = None

    def detect_human(self, img: Image.Image) -> bool:
        """Detect a visible face or upright pedestrian before plant classification."""
        rgb = np.asarray(img)
        height, width = rgb.shape[:2]
        scale = min(1.0, 800.0 / max(height, width))
        if scale < 1.0:
            rgb = cv2.resize(rgb, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        if self._face_cascade is not None:
            faces = self._face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(24, 24)
            )
            if len(faces) > 0:
                return True
        if self._people_hog is not None:
            people, _ = self._people_hog.detectMultiScale(
                gray,
                hitThreshold=0.0,
                winStride=(8, 8),
                padding=(8, 8),
                scale=1.05,
            )
            return len(people) > 0
        return False

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
        """Layer 4 — fraction of pixels matching green or chlorotic yellow leaf tissue.

        Green/yellow foliage is required so red fruit, flowers, skin, or other colorful
        objects cannot pass the leaf upload gate by color alone.
        """
        img_arr = np.array(img)

        if HAS_CV2:
            hsv = cv2.cvtColor(img_arr, cv2.COLOR_RGB2HSV)
            # Green and chlorotic-yellow foliage; hue 10-105 excludes red/orange objects and flowers.
            mask_green = cv2.inRange(hsv, np.array([10, 25, 25]), np.array([105, 255, 255]))

            # Sky-blue exclusion — pixels that are sky-blue are NOT plant tissue
            sky_mask = cv2.inRange(hsv, np.array([95, 40, 100]), np.array([130, 255, 255]))

            combined = mask_green & ~sky_mask
            ratio = np.count_nonzero(combined) / float(img_arr.shape[0] * img_arr.shape[1])
        else:
            r = img_arr[:, :, 0].astype(np.float32)
            g = img_arr[:, :, 1].astype(np.float32)
            b = img_arr[:, :, 2].astype(np.float32)
            max_c = np.maximum(np.maximum(r, g), b)
            min_c = np.minimum(np.minimum(r, g), b)
            diff = max_c - min_c

            # Green and chlorotic-yellow foliage only.
            green_mask = (diff >= 12) & (
                ((g > r * 0.85) & (g > b * 1.05) & (g > 30)) |
                ((r > 70) & (g > 65) & (b < 140) & (r + g > b * 1.6) & (np.abs(r - g) < 55))
            )
            # Exclude sky-blue from green plant mask
            sky_mask_np = (b > r * 1.2) & (b > g * 1.1) & (b > 80)
            green_mask = green_mask & ~sky_mask_np

            plant_mask = green_mask
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

        # Reject portraits before color heuristics: skin, hair, and green outdoor
        # backgrounds can otherwise satisfy the foliage-pixel threshold.
        if HAS_CV2 and self.detect_human(img):
            return {
                "is_valid": False,
                "status": PredictionStatus.NOT_A_PLANT.value,
                "reason": "A person was detected. Please upload a close-up photo of a plant leaf.",
                "foliage_ratio": 0.0,
                "image": img,
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
                    "Please upload a colour photo focused on a plant leaf."
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
                    "The image does not appear to contain a recognisable plant leaf."
                ),
                "foliage_ratio": foliage_ratio,
                "image": img,
            }

        # ── Layers 5, 6, 7 (cv2 required) ────────────────────────────────────
        if HAS_CV2:
            variance, edge_density = self.evaluate_texture_and_edges(img)

            # Layers 5 & 6: Texture variance and edge density check.
            # Flat solid fills and pure digital graphics have near-zero variance (< 4.0)
            # AND zero edge density (< 0.0005). Genuine leaves (even smooth close-ups or soft-focus)
            # have natural organic variation and must not be rejected.
            if variance < self.texture_variance_threshold and edge_density < self.edge_density_min:
                return {
                    "is_valid": False,
                    "status": PredictionStatus.NOT_A_PLANT.value,
                    "reason": (
                        f"Image appears to be a flat graphic or blank fill "
                        f"(pixel variance {variance:.1f}, edge density {edge_density:.4f}), "
                        "not a natural plant photo."
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
                        "leaf."
                    ),
                    "foliage_ratio": foliage_ratio,
                    "image": img,
                }

            # Layer 7b: green-channel dominance — only rejects if min_green_dominance > 0
            if self.min_green_dominance > 0.0:
                green_dom = self.evaluate_green_dominance(img)
                if green_dom < self.min_green_dominance:
                    return {
                        "is_valid": False,
                        "status": PredictionStatus.NOT_A_PLANT.value,
                        "reason": (
                            f"Image does not contain sufficient green plant tissue "
                            f"(green dominance score: {green_dom:.3f}). "
                            "Please upload a photo focused on a plant leaf."
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
