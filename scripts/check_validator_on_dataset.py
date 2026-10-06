"""
Sample the PlantVillage folders and report how many real plant images the
ImageValidator wrongly rejects. Use it to tune edge_density_min /
texture_variance_threshold before training or demoing.

Usage:
    python scripts/check_validator_on_dataset.py [--data-dir data/raw/PlantVillage]
        [--per-class 20] [--edge-density-min 0.03] [--texture-variance 80]
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.dataset_index import IMAGE_EXTENSIONS, NOT_A_PLANT_LABEL  # noqa: E402
from src.preprocessing.image_validator import ImageValidator  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="data/raw/PlantVillage")
    parser.add_argument("--per-class", type=int, default=20)
    parser.add_argument("--edge-density-min", type=float, default=0.03)
    parser.add_argument("--texture-variance", type=float, default=80.0)
    parser.add_argument("--show", type=int, default=20, help="How many rejections to print")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = ROOT_DIR / data_dir
    if not data_dir.is_dir():
        raise SystemExit(f"Dataset directory not found: {data_dir}")

    validator = ImageValidator(
        edge_density_min=args.edge_density_min,
        texture_variance_threshold=args.texture_variance,
    )

    checked = 0
    rejected = []
    per_class_rejected = Counter()
    per_class_checked = Counter()
    for class_dir in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        if class_dir.name == NOT_A_PLANT_LABEL or class_dir.name.startswith("."):
            continue
        images = sorted(
            p for p in class_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS
        )[: args.per_class]
        for path in images:
            checked += 1
            per_class_checked[class_dir.name] += 1
            result = validator.validate(str(path))
            if not result["is_valid"]:
                per_class_rejected[class_dir.name] += 1
                rejected.append((class_dir.name, path.name, result["reason"]))

    rate = len(rejected) / max(checked, 1)
    print(f"Checked {checked} images; rejected {len(rejected)} ({rate:.1%})")
    for name, count in per_class_rejected.most_common():
        print(f"  {name}: {count}/{per_class_checked[name]} rejected")
    print("\nSample rejections:")
    for name, fname, reason in rejected[: args.show]:
        print(f"  {name}/{fname}: {reason}")
    if rate > 0.02:
        print(
            "\nHigh false-rejection rate. Try --edge-density-min 0.015 first, "
            "then lower --texture-variance if needed."
        )


if __name__ == "__main__":
    main()
