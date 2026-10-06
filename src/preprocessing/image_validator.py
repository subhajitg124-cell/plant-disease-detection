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
    def __init__(
        self,
        min_width: int = 32,
        min_height: int = 32,
        foliage_green_threshold: float = 0.08,
        texture_variance_threshold: float = 80.0,
        edge_density_min: float = 0.03,
        max_dim: int = 4096
    ):
        self.min_width = min_width
        self.min_height = min_height
        self.foliage_green_threshold = foliage_green_threshold
        self.texture_variance_threshold = texture_variance_threshold
        self.edge_density_min = edge_density_min
        self.max_dim = max_dim

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

    def evaluate_plant_foliage_ratio(self, img: Image.Image) -> float:
        img_arr = np.array(img)

        if HAS_CV2:
            hsv = cv2.cvtColor(img_arr, cv2.COLOR_RGB2HSV)
            # Green/yellow/brown foliar tissue and stem (10-105 hue, with saturation)
            lower_green = np.array([10, 25, 20])
            upper_green = np.array([105, 255, 255])
            mask_green = cv2.inRange(hsv, lower_green, upper_green)

            # Red fruit tissue (tomato, apple, strawberry) — hue wraps at 0/180
            lower_red1 = np.array([0, 50, 40])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([160, 50, 40])
            upper_red2 = np.array([180, 255, 255])
            mask_red = cv2.inRange(hsv, lower_red1, upper_red1) | cv2.inRange(hsv, lower_red2, upper_red2)

            # Pink / purple flower petals (130-165 hue)
            lower_flower = np.array([130, 20, 60])
            upper_flower = np.array([165, 255, 255])
            mask_flower = cv2.inRange(hsv, lower_flower, upper_flower)

            combined = mask_green | mask_red | mask_flower
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

    def validate(self, input_source: Union[str, Image.Image, np.ndarray]) -> Dict[str, Any]:
        ok, img, msg = self.validate_file_integrity(input_source)
        if not ok or img is None:
            return {
                "is_valid": False,
                "status": PredictionStatus.NOT_A_PLANT.value,
                "reason": msg,
                "foliage_ratio": 0.0,
                "image": None
            }

        ok_dim, dim_msg = self.validate_dimensions(img)
        if not ok_dim:
            return {
                "is_valid": False,
                "status": PredictionStatus.NOT_A_PLANT.value,
                "reason": dim_msg,
                "foliage_ratio": 0.0,
                "image": None
            }

        foliage_ratio = self.evaluate_plant_foliage_ratio(img)
        if foliage_ratio < self.foliage_green_threshold:
            return {
                "is_valid": False,
                "status": PredictionStatus.NOT_A_PLANT.value,
                "reason": (
                    f"Plant tissue coverage ratio ({foliage_ratio:.3f}) below threshold "
                    f"({self.foliage_green_threshold:.3f}). Image does not appear to contain "
                    "a recognisable plant leaf, fruit, or flower."
                ),
                "foliage_ratio": foliage_ratio,
                "image": img
            }
        if HAS_CV2:
            variance, edge_density = self.evaluate_texture_and_edges(img)
            if variance < self.texture_variance_threshold:
                return {
                    "is_valid": False,
                    "status": PredictionStatus.NOT_A_PLANT.value,
                    "reason": f"Image lacks natural leaf texture (variance {variance:.1f} < {self.texture_variance_threshold:.1f}). Please upload a real photo of a plant leaf, fruit, or flower.",
                    "foliage_ratio": foliage_ratio,
                    "image": img
                }
            if edge_density < self.edge_density_min:
                return {
                    "is_valid": False,
                    "status": PredictionStatus.NOT_A_PLANT.value,
                    "reason": f"Image appears to be a plain colour or graphic (edge density {edge_density:.3f} < {self.edge_density_min:.3f}), not a plant photo.",
                    "foliage_ratio": foliage_ratio,
                    "image": img
                }

        return {
            "is_valid": True,
            "status": PredictionStatus.SUPPORTED.value,
            "reason": "Image passed all plant validation checks.",
            "foliage_ratio": foliage_ratio,
            "image": img
        }
