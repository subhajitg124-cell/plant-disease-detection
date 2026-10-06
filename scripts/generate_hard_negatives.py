"""
Generate diverse synthetic hard-negative and non-plant images for:
1. Training: data/raw/PlantVillage/Not_a_plant/ (hard negatives like grass, green fabric, broccoli, moss, ferns, solid greens with texture, geometric shapes, green shirts/walls, non-leaf organic objects)
2. Evaluation: data/eval/not_a_plant_holdout/ (150+ diverse non-plant images across hard and standard negatives)

Usage:
    python scripts/generate_hard_negatives.py [--train-count 200] [--holdout-count 150]
"""
import argparse
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


def create_grass_texture(h=224, w=224, seed=0) -> np.ndarray:
    """Simulate close-up dense lawn/grass blades."""
    rng = np.random.default_rng(seed)
    arr = np.zeros((h, w, 3), dtype=np.float32)
    # Base earthy green
    arr[:, :, 0] = 30 + rng.integers(-10, 10)
    arr[:, :, 1] = 120 + rng.integers(-15, 15)
    arr[:, :, 2] = 25 + rng.integers(-8, 8)

    # Vertical blade lines
    for _ in range(300):
        c = rng.integers(0, w)
        width = rng.integers(1, 4)
        length = rng.integers(h // 3, h)
        r_start = rng.integers(0, h - length + 1)
        shade_g = rng.integers(90, 210)
        shade_r = rng.integers(20, 60)
        shade_b = rng.integers(10, 40)
        arr[r_start:r_start+length, max(0, c-width):min(w, c+width), 0] = shade_r
        arr[r_start:r_start+length, max(0, c-width):min(w, c+width), 1] = shade_g
        arr[r_start:r_start+length, max(0, c-width):min(w, c+width), 2] = shade_b

    # Add high-frequency noise
    arr += rng.normal(0, 15, (h, w, 3))
    return np.clip(arr, 0, 255).astype(np.uint8)


def create_green_fabric(h=224, w=224, seed=0) -> np.ndarray:
    """Simulate green fabric weave (t-shirt / cotton cloth)."""
    rng = np.random.default_rng(seed)
    arr = np.zeros((h, w, 3), dtype=np.float32)
    base_g = rng.integers(110, 180)
    base_r = rng.integers(30, 70)
    base_b = rng.integers(30, 80)
    arr[:, :, 0] = base_r
    arr[:, :, 1] = base_g
    arr[:, :, 2] = base_b

    # Weave pattern (grid stripes)
    weave_x = np.sin(np.linspace(0, 40 * np.pi, w)).reshape(1, w, 1)
    weave_y = np.cos(np.linspace(0, 40 * np.pi, h)).reshape(h, 1, 1)
    arr += (weave_x * weave_y) * 25.0
    arr += rng.normal(0, 10, (h, w, 3))
    return np.clip(arr, 0, 255).astype(np.uint8)


def create_broccoli_texture(h=224, w=224, seed=0) -> np.ndarray:
    """Simulate dense broccoli florets (granular bumpy green)."""
    rng = np.random.default_rng(seed)
    arr = np.zeros((h, w, 3), dtype=np.float32)
    arr[:, :, 0] = 35
    arr[:, :, 1] = 100
    arr[:, :, 2] = 30

    # Bumps / beads
    for _ in range(400):
        y = rng.integers(0, h)
        x = rng.integers(0, w)
        rad = rng.integers(3, 8)
        color_g = rng.integers(70, 160)
        color_r = rng.integers(20, 50)
        y1, y2 = max(0, y-rad), min(h, y+rad)
        x1, x2 = max(0, x-rad), min(x+rad, w)
        arr[y1:y2, x1:x2, 0] = color_r
        arr[y1:y2, x1:x2, 1] = color_g
        arr[y1:y2, x1:x2, 2] = 25

    arr += rng.normal(0, 18, (h, w, 3))
    return np.clip(arr, 0, 255).astype(np.uint8)


def create_moss_texture(h=224, w=224, seed=0) -> np.ndarray:
    """Simulate moss on bark/stone."""
    rng = np.random.default_rng(seed)
    arr = np.zeros((h, w, 3), dtype=np.float32)
    # Dark brown / gray stone base
    arr[:, :, 0] = 70 + rng.integers(-15, 15)
    arr[:, :, 1] = 65 + rng.integers(-15, 15)
    arr[:, :, 2] = 55 + rng.integers(-15, 15)

    # Moss patches
    for _ in range(15):
        cy = rng.integers(0, h)
        cx = rng.integers(0, w)
        rx = rng.integers(20, 60)
        ry = rng.integers(20, 60)
        y, x = np.ogrid[:h, :w]
        mask = ((y - cy)**2 / ry**2 + (x - cx)**2 / rx**2) <= 1
        arr[mask, 0] = rng.integers(30, 60)
        arr[mask, 1] = rng.integers(120, 190)
        arr[mask, 2] = rng.integers(20, 45)

    arr += rng.normal(0, 20, (h, w, 3))
    return np.clip(arr, 0, 255).astype(np.uint8)


def create_fern_pattern(h=224, w=224, seed=0) -> np.ndarray:
    """Simulate decorative non-crop fern fronds / fractal-like repetitive green spikes."""
    rng = np.random.default_rng(seed)
    img = Image.new("RGB", (w, h), color=(rng.integers(20, 50), rng.integers(20, 50), rng.integers(20, 50)))
    draw = ImageDraw.Draw(img)

    for spine_x in [w//4, w//2, 3*w//4]:
        for y in range(10, h-10, 12):
            length = rng.integers(20, 45)
            draw.line([(spine_x, y), (spine_x - length, y - 8)], fill=(rng.integers(30, 60), rng.integers(130, 200), rng.integers(20, 50)), width=3)
            draw.line([(spine_x, y), (spine_x + length, y - 8)], fill=(rng.integers(30, 60), rng.integers(130, 200), rng.integers(20, 50)), width=3)

    arr = np.array(img).astype(np.float32)
    arr += rng.normal(0, 15, (h, w, 3))
    return np.clip(arr, 0, 255).astype(np.uint8)


def create_general_object(category: str, h=224, w=224, seed=0) -> np.ndarray:
    """Create geometric/household/urban/animal object simulations."""
    rng = np.random.default_rng(seed)
    bg_color = (rng.integers(160, 240), rng.integers(160, 240), rng.integers(160, 240))
    img = Image.new("RGB", (w, h), color=bg_color)
    draw = ImageDraw.Draw(img)

    if category == "car":
        draw.rectangle([30, 90, 190, 160], fill=(rng.integers(180, 250), rng.integers(20, 50), rng.integers(20, 50)))
        draw.polygon([(60, 90), (90, 50), (140, 50), (170, 90)], fill=(rng.integers(180, 250), rng.integers(20, 50), rng.integers(20, 50)))
        draw.ellipse([50, 140, 90, 180], fill=(30, 30, 30))
        draw.ellipse([130, 140, 170, 180], fill=(30, 30, 30))
    elif category == "person_shirt":
        # Green shirt on a human silhouette
        draw.ellipse([80, 20, 144, 84], fill=(220, 180, 140)) # face
        draw.polygon([(40, 90), (184, 90), (200, 220), (24, 220)], fill=(rng.integers(20, 60), rng.integers(140, 220), rng.integers(30, 70)))
    elif category == "building":
        draw.rectangle([40, 40, 180, 224], fill=(120, 130, 140))
        for r in range(60, 200, 30):
            for c in range(60, 160, 30):
                draw.rectangle([c, r, c+18, r+20], fill=(220, 230, 100))
    elif category == "cartoon_graphic":
        draw.ellipse([40, 40, 184, 184], fill=(255, 220, 0))
        draw.ellipse([70, 70, 95, 95], fill=(0, 0, 0))
        draw.ellipse([129, 70, 154, 95], fill=(0, 0, 0))
        draw.arc([70, 90, 154, 150], 0, 180, fill=(0, 0, 0), width=5)
    elif category == "screenshot_ui":
        draw.rectangle([10, 10, 214, 40], fill=(50, 100, 220))
        draw.rectangle([10, 50, 214, 214], fill=(245, 245, 250))
        for line_y in range(70, 190, 20):
            draw.line([(25, line_y), (rng.integers(100, 190), line_y)], fill=(80, 80, 90), width=6)
    else: # animal / furniture
        draw.ellipse([40, 70, 180, 170], fill=(rng.integers(120, 180), rng.integers(80, 120), rng.integers(40, 70)))
        draw.ellipse([140, 40, 190, 90], fill=(rng.integers(120, 180), rng.integers(80, 120), rng.integers(40, 70)))

    arr = np.array(img).astype(np.float32)
    arr += rng.normal(0, 12, (h, w, 3))
    return np.clip(arr, 0, 255).astype(np.uint8)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-dir", default="data/raw/PlantVillage/Not_a_plant")
    parser.add_argument("--holdout-dir", default="data/eval/not_a_plant_holdout")
    parser.add_argument("--train-count", type=int, default=300, help="Number of synthetic hard negatives for training")
    parser.add_argument("--holdout-count", type=int, default=150, help="Number of holdout test images")
    args = parser.parse_args()

    train_dir = ROOT_DIR / args.train_dir
    holdout_dir = ROOT_DIR / args.holdout_dir
    train_dir.mkdir(parents=True, exist_ok=True)
    holdout_dir.mkdir(parents=True, exist_ok=True)

    generators = [
        ("grass", create_grass_texture),
        ("fabric", create_green_fabric),
        ("broccoli", create_broccoli_texture),
        ("moss", create_moss_texture),
        ("fern", create_fern_pattern),
        ("person_shirt", lambda seed: create_general_object("person_shirt", seed=seed)),
        ("car", lambda seed: create_general_object("car", seed=seed)),
        ("building", lambda seed: create_general_object("building", seed=seed)),
        ("cartoon", lambda seed: create_general_object("cartoon_graphic", seed=seed)),
        ("screenshot", lambda seed: create_general_object("screenshot_ui", seed=seed)),
        ("animal", lambda seed: create_general_object("animal", seed=seed)),
    ]

    print(f"Generating {args.train_count} synthetic hard-negative training images in {train_dir}...")
    for i in range(args.train_count):
        name, gen_fn = generators[i % len(generators)]
        arr = gen_fn(seed=1000 + i)
        Image.fromarray(arr).save(train_dir / f"hard_neg_{name}_{i:04d}.jpg", quality=92)

    print(f"Generating {args.holdout_count} holdout evaluation images in {holdout_dir}...")
    for i in range(args.holdout_count):
        name, gen_fn = generators[i % len(generators)]
        arr = gen_fn(seed=5000 + i)
        Image.fromarray(arr).save(holdout_dir / f"holdout_{name}_{i:04d}.jpg", quality=92)

    print("Completed hard-negative and holdout dataset generation.")


if __name__ == "__main__":
    main()
