"""Standard-library helpers for indexing and splitting image-folder datasets."""
import csv
import random
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def load_class_mapping(mapping_path: Path) -> Dict[int, Dict[str, str]]:
    if not mapping_path.exists():
        raise FileNotFoundError(f"Class mapping file not found: {mapping_path}")

    mapping: Dict[int, Dict[str, str]] = {}
    with mapping_path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            class_id = int(row["class_id"])
            label = row.get("original_label", "").strip()
            if not label:
                raise ValueError(f"Class {class_id} has no original_label in {mapping_path}")
            if class_id in mapping:
                raise ValueError(f"Duplicate class_id {class_id} in {mapping_path}")
            mapping[class_id] = {
                "original_label": label,
                "canonical_id": row.get("canonical_id", ""),
                "plant": row.get("plant", ""),
                "disease": row.get("disease", ""),
            }

    if not mapping:
        raise ValueError(f"No class rows found in {mapping_path}")
    return mapping


def discover_class_images(
    data_dir: Path,
    mapping: Dict[int, Dict[str, str]],
    max_images_per_class: Optional[int] = None,
) -> Tuple[List[int], Dict[int, List[Path]], List[str]]:
    if not data_dir.is_dir():
        raise FileNotFoundError(f"PlantVillage image directory not found: {data_dir}")

    label_to_id = {
        meta["original_label"]: class_id for class_id, meta in mapping.items()
    }
    unexpected = sorted(
        entry.name
        for entry in data_dir.iterdir()
        if entry.is_dir() and entry.name not in label_to_id and not entry.name.startswith(".")
    )
    if unexpected:
        raise ValueError(
            "Unexpected class folder(s) under PlantVillage: " + ", ".join(unexpected)
        )

    images_by_id: Dict[int, List[Path]] = {}
    missing: List[str] = []
    for class_id, meta in sorted(mapping.items()):
        class_dir = data_dir / meta["original_label"]
        images = sorted(
            path for path in class_dir.glob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        ) if class_dir.is_dir() else []
        if not images:
            missing.append(meta["original_label"])
            continue
        if max_images_per_class is not None:
            images = images[:max_images_per_class]
        if len(images) < 3:
            raise ValueError(
                f"{meta['original_label']} has only {len(images)} image(s); "
                "at least 3 are needed for train/validation/test splits."
            )
        images_by_id[class_id] = images

    if len(images_by_id) < 2:
        raise ValueError("At least two classes with images are required for training.")
    return sorted(images_by_id), images_by_id, missing


def split_images(
    class_ids: Sequence[int],
    images_by_id: Dict[int, List[Path]],
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> Tuple[List[Tuple[Path, int]], List[Tuple[Path, int]], List[Tuple[Path, int]]]:
    if val_ratio <= 0 or test_ratio <= 0 or val_ratio + test_ratio >= 1:
        raise ValueError("Validation and test ratios must be positive and sum to less than 1.")

    rng = random.Random(seed)
    train_records: List[Tuple[Path, int]] = []
    val_records: List[Tuple[Path, int]] = []
    test_records: List[Tuple[Path, int]] = []

    for class_id in class_ids:
        paths = list(images_by_id[class_id])
        rng.shuffle(paths)
        count = len(paths)
        n_val = max(1, int(round(count * val_ratio)))
        n_test = max(1, int(round(count * test_ratio)))
        while n_val + n_test >= count:
            if n_val >= n_test and n_val > 1:
                n_val -= 1
            elif n_test > 1:
                n_test -= 1
            else:
                raise ValueError(
                    f"Cannot split {count} images for class ID {class_id} "
                    "into train/validation/test."
                )

        val_paths = paths[:n_val]
        test_paths = paths[n_val:n_val + n_test]
        train_paths = paths[n_val + n_test:]
        train_records.extend((path, class_id) for path in train_paths)
        val_records.extend((path, class_id) for path in val_paths)
        test_records.extend((path, class_id) for path in test_paths)

    return train_records, val_records, test_records