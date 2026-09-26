from typing import Union, Tuple, Optional, List
import numpy as np
from PIL import Image

try:
    import torch
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


class ImageTransformer:
    def __init__(
        self,
        target_size: Tuple[int, int] = (224, 224),
        mean: Union[Tuple[float, float, float], np.ndarray] = IMAGENET_MEAN,
        std: Union[Tuple[float, float, float], np.ndarray] = IMAGENET_STD,
        augment: bool = False
    ):
        self.target_size = target_size
        self.mean = np.array(mean, dtype=np.float32)
        self.std = np.array(std, dtype=np.float32)
        self.augment = augment

    def load_image(self, input_source: Union[str, Image.Image, np.ndarray]) -> Image.Image:
        if isinstance(input_source, str):
            img = Image.open(input_source).convert("RGB")
        elif isinstance(input_source, Image.Image):
            img = input_source.convert("RGB")
        elif isinstance(input_source, np.ndarray):
            if input_source.ndim == 3 and input_source.shape[2] == 3:
                img = Image.fromarray(input_source.astype(np.uint8)).convert("RGB")
            else:
                raise ValueError(f"Invalid NumPy image shape: {input_source.shape}")
        else:
            raise TypeError(f"Unsupported image input type: {type(input_source)}")
        return img

    def resize(self, img: Image.Image) -> Image.Image:
        return img.resize(self.target_size, Image.Resampling.BICUBIC)

    def apply_augmentations(self, img: Image.Image) -> Image.Image:
        if not self.augment:
            return img

        if np.random.rand() > 0.5:
            img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)

        if np.random.rand() > 0.5:
            img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)

        angle = np.random.uniform(-15, 15)
        img = img.rotate(angle, resample=Image.Resampling.BICUBIC)

        return img

    def to_array(self, img: Image.Image) -> np.ndarray:
        arr = np.array(img, dtype=np.float32) / 255.0
        arr = (arr - self.mean) / self.std
        arr = np.transpose(arr, (2, 0, 1))
        return arr

    def to_tensor(self, arr: np.ndarray):
        if HAS_TORCH:
            tensor = torch.from_numpy(arr).float()
            return tensor
        return arr

    def transform(self, input_source: Union[str, Image.Image, np.ndarray], return_tensor: bool = True):
        img = self.load_image(input_source)
        img = self.resize(img)
        if self.augment:
            img = self.apply_augmentations(img)

        arr = self.to_array(img)

        if return_tensor and HAS_TORCH:
            return self.to_tensor(arr)
        return arr


def get_default_transforms(target_size: Tuple[int, int] = (224, 224), augment: bool = False) -> ImageTransformer:
    return ImageTransformer(target_size=target_size, augment=augment)
