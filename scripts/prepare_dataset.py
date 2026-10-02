"""Create real, stratified train/validation/test CSVs from PlantVillage images."""
import csv
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.dataset_index import discover_class_images, load_class_mapping, split_images


def main():
    mapping_path = ROOT_DIR / "data" / "metadata" / "plantvillage_class_mapping.csv"
    image_root = ROOT_DIR / "data" / "raw" / "PlantVillage"
    output_dir = ROOT_DIR / "data" / "processed"

    mapping = load_class_mapping(mapping_path)
    class_ids, images_by_id, missing_classes = discover_class_images(image_root, mapping)
    train_records, val_records, test_records = split_images(
        class_ids, images_by_id, val_ratio=0.15, test_ratio=0.15, seed=42
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    splits = {
        "train": train_records,
        "val": val_records,
        "test": test_records,
    }
    fieldnames = [
        "sample_id",
        "class_id",
        "canonical_id",
        "plant",
        "disease",
        "original_label",
        "image_path",
        "split",
    ]

    for split_name, records in splits.items():
        output_path = output_dir / f"{split_name}.csv"
        with output_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for image_path, class_id in records:
                class_info = mapping[class_id]
                writer.writerow({
                    "sample_id": f"{class_info['canonical_id']}_{image_path.stem}",
                    "class_id": class_id,
                    "canonical_id": class_info["canonical_id"],
                    "plant": class_info["plant"],
                    "disease": class_info["disease"],
                    "original_label": class_info["original_label"],
                    "image_path": image_path.relative_to(ROOT_DIR).as_posix(),
                    "split": split_name,
                })
        print(f"Wrote {len(records)} real image records to {output_path}")

    if missing_classes:
        print("Classes without images: " + ", ".join(missing_classes))
    print(f"Prepared splits for {len(class_ids)} available classes.")


if __name__ == "__main__":
    main()