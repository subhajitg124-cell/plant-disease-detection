"""
Measure how many non-plant holdout images the full pipeline rejects.

Usage:
    python scripts/evaluate_not_a_plant_holdout.py [--holdout-dir data/eval/not_a_plant_holdout]

Exit code 0 if the rejection rate is >= 90%, otherwise 1.
"""
import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.dataset_index import IMAGE_EXTENSIONS  # noqa: E402
from src.pipeline import PlantDiseasePipeline  # noqa: E402

# Compared case-insensitively: the enum uses "not_a_plant", the gate uses uppercase.
REJECTED_STATUSES = {"not_a_plant", "rejected_low_confidence", "rejected_invalid_image"}
PASS_RATE = 0.90


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holdout-dir", default="data/eval/not_a_plant_holdout/")
    args = parser.parse_args()

    holdout = Path(args.holdout_dir)
    if not holdout.is_absolute():
        holdout = ROOT_DIR / holdout
    if not holdout.is_dir():
        print(f"Holdout directory not found: {holdout}")
        sys.exit(1)

    files = sorted(
        p for p in holdout.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not files:
        print(f"No images found in {holdout}")
        sys.exit(1)

    pipeline = PlantDiseasePipeline()
    rejected = 0
    wrong = []
    for fpath in files:
        try:
            result = pipeline.predict_and_advise(str(fpath))
            status, confidence = str(result.status), float(result.confidence)
        except Exception as error:  # a crash is not a rejection
            status, confidence = f"ERROR: {error}", 0.0
        if status.lower() in REJECTED_STATUSES:
            rejected += 1
        else:
            wrong.append((fpath.name, status, confidence))

    for name, status, confidence in wrong:
        print(f"  WRONG: {name}  status={status}  confidence={confidence:.3f}")

    total = len(files)
    rate = rejected / total
    print(f"Rejection rate: {rejected}/{total} ({rate:.1%})")
    print(f"Wrongly classified: {len(wrong)} images")
    sys.exit(0 if rate >= PASS_RATE else 1)


if __name__ == "__main__":
    main()
