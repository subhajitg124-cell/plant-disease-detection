"""Synthetic image fixtures shared by tests.

The ImageValidator rejects flat, texture-free images, so "leaf" fixtures must
carry noise and vein-like lines to count as plant photos.
"""
import numpy as np


def make_textured_leaf(h: int = 224, w: int = 224, base=(40, 150, 30), seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    arr = np.zeros((h, w, 3), dtype=np.int16)
    arr[:, :] = base
    arr += rng.integers(-40, 40, size=(h, w, 1))
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    vein = tuple(int(c * 0.45) for c in base)
    arr[::8, :, :] = vein
    arr[:, ::8, :] = vein
    return arr
