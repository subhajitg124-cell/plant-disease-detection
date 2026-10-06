"""
Build the Not_a_plant reject-class folder used by src/vision/train.py.

Sources (use either or both):
  --source DIR      Folder tree of non-plant images, e.g. an ImageNet subset
                    (animals, vehicles, household objects). Searched recursively.
  --caltech256      Download Caltech-256 via torchvision and sample from it,
                    skipping plant-like categories.

Usage:
    python scripts/build_not_a_plant_dataset.py --source D:/imagenet_subset --count 800
    python scripts/build_not_a_plant_dataset.py --caltech256 --count 800

Tip: also add "hard negatives" (grass, green fabric, broccoli, ferns, green
walls) via --source, otherwise the CNN will only learn to reject easy images.
Images are resized so the longest side is <= 256 px and saved as JPEG.
"""
import argparse
import random
import sys
from pathlib import Path
from typing import List

from PIL import Image

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.dataset_index import IMAGE_EXTENSIONS, NOT_A_PLANT_LABEL  # noqa: E402

# Caltech-256 categories that contain plants/flowers/fruit; never use as negatives.
PLANT_LIKE_KEYWORDS = (
    "grass", "leaf", "mushroom", "flower", "tree", "fern", "broccoli",
    "cucumber", "watermelon", "strawberry", "tomato", "sunflower",
    "palm", "plant", "rose", "daisy", "lotus", "cactus", "grape", "bonsai",
    "orchid", "lily", "vegetable", "fruit", "corn", "pepper", "apple",
    "peach", "potato",
)


def save_resized(src: Image.Image, dest: Path) -> None:
    img = src.convert("RGB")
    img.thumbnail((256, 256))
    img.save(dest, format="JPEG", quality=90)


def collect_from_source(source: Path) -> List[Path]:
    return [p for p in source.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS]


def collect_from_caltech(download_root: Path, count: int, rng: random.Random):
    try:
        from torchvision.datasets import Caltech256
    except ImportError as error:
        raise SystemExit("torchvision is required for --caltech256") from error
    dataset = Caltech256(root=str(download_root), download=True)
    categories = list(dataset.categories)
    keep = {
        i for i, name in enumerate(categories)
        if not any(k in name.lower() for k in PLANT_LIKE_KEYWORDS)
    }
    indices = [i for i, label in enumerate(dataset.y) if label in keep]
    rng.shuffle(indices)
    for idx in indices[:count]:
        image, _ = dataset[idx]
        yield image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append", default=[], help="Folder of non-plant images (repeatable)")
    parser.add_argument("--caltech256", action="store_true")
    parser.add_argument("--count", type=int, default=800, help="Images to take from each source")
    parser.add_argument("--output", default="data/raw/PlantVillage/" + NOT_A_PLANT_LABEL)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not args.source and not args.caltech256:
        raise SystemExit("Provide --source DIR and/or --caltech256.")

    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT_DIR / output
    output.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    written = 0

    for source in args.source:
        files = collect_from_source(Path(source))
        rng.shuffle(files)
        for path in files[: args.count]:
            try:
                with Image.open(path) as img:
                    save_resized(img, output / f"src_{written:05d}.jpg")
                written += 1
            except Exception as error:
                print(f"Skipping {path}: {error}")

    if args.caltech256:
        for image in collect_from_caltech(ROOT_DIR / "data" / "external" / "caltech256", args.count, rng):
            save_resized(image, output / f"caltech_{written:05d}.jpg")
            written += 1

    print(f"Wrote {written} images to {output}")
    if written < 500:
        print("Warning: fewer than ~500 images; the reject class may be weak.")


if __name__ == "__main__":
    main()
