"""Evaluate the live image classifier on the deterministic held-out image split."""
import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
import sys
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.evaluation.metrics import calculate_metrics
from src.pipeline import PlantDiseasePipeline
from src.vision.train import discover_class_images, load_class_mapping, split_images


def evaluate(
    data_dir: Path,
    mapping_path: Path,
    checkpoint_path: Path,
    reports_dir: Path,
    seed: int = 42,
) -> Dict[str, Any]:
    mapping = load_class_mapping(mapping_path)
    class_ids, images_by_id, missing_classes = discover_class_images(data_dir, mapping)
    _, _, test_records = split_images(
        class_ids, images_by_id, val_ratio=0.15, test_ratio=0.15, seed=seed
    )

    pipeline = PlantDiseasePipeline(
        model_path=str(checkpoint_path),
        class_mapping_path=str(mapping_path),
        kb_path=str(ROOT_DIR / "data" / "knowledge_base" / "agricultural_documents.json"),
        store_dir=str(ROOT_DIR / "models" / "vector_index"),
    )
    classifier = pipeline.classifier
    if not classifier.checkpoint_loaded or not classifier.checkpoint_metadata.get("trained_on_images"):
        raise RuntimeError(
            f"No real-image training checkpoint found at {checkpoint_path}. "
            "Train with: .venv\\Scripts\\python.exe -m src.vision.train"
        )

    canonical_to_id = {
        meta["canonical_id"]: class_id for class_id, meta in mapping.items()
    }
    unknown_id = max(mapping) + 1
    y_true: List[int] = []
    y_pred: List[int] = []
    by_class: Dict[int, Dict[str, int]] = {
        class_id: {"total": 0, "correct": 0} for class_id in class_ids
    }
    unknown_predictions = 0

    for index, (image_path, true_class_id) in enumerate(test_records, start=1):
        prediction = classifier.predict(str(image_path), extract_embedding=False)
        predicted_class_id = canonical_to_id.get(prediction.canonical_id, unknown_id)
        if predicted_class_id not in classifier.active_class_ids:
            predicted_class_id = unknown_id
        y_true.append(true_class_id)
        y_pred.append(predicted_class_id)
        by_class[true_class_id]["total"] += 1
        if predicted_class_id == true_class_id:
            by_class[true_class_id]["correct"] += 1
        if predicted_class_id == unknown_id:
            unknown_predictions += 1

        if index % 500 == 0:
            print(f"Evaluated {index}/{len(test_records)} held-out images.")

    metrics = calculate_metrics(y_true, y_pred, num_classes=unknown_id + 1)
    metrics.pop("top3_accuracy", None)
    metrics.pop("top5_accuracy", None)
    metrics["unknown_predictions"] = unknown_predictions
    metrics["active_class_count"] = len(classifier.active_class_ids)
    metrics["active_class_ids"] = classifier.active_class_ids
    metrics["missing_classes"] = missing_classes
    metrics["per_class_accuracy"] = {
        str(class_id): {
            "label": mapping[class_id]["original_label"],
            "samples": values["total"],
            "accuracy": values["correct"] / values["total"] if values["total"] else 0.0,
        }
        for class_id, values in by_class.items()
    }

    reports_dir.mkdir(parents=True, exist_ok=True)
    json_path = reports_dir / "plantvillage_test_report.json"
    markdown_path = reports_dir / "plantvillage_test_report.md"
    json_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    markdown = [
        "# PlantVillage Held-Out Test Results",
        "",
        f"- Real test images: {metrics['total_samples']}",
        f"- Classes trained: {metrics['active_class_count']} of {len(mapping)}",
        f"- Accuracy: {metrics['accuracy']:.2%}",
        f"- Macro F1: {metrics['f1_macro']:.4f}",
        f"- Predictions outside trained classes: {unknown_predictions}",
        "",
        "## Per-class accuracy",
        "",
        "| Class ID | Label | Samples | Accuracy |",
        "| ---: | --- | ---: | ---: |",
    ]
    for class_id, values in metrics["per_class_accuracy"].items():
        markdown.append(
            f"| {class_id} | {values['label']} | {values['samples']} | "
            f"{values['accuracy']:.2%} |"
        )
    markdown_path.write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(f"Accuracy: {metrics['accuracy']:.2%}; macro F1: {metrics['f1_macro']:.4f}")
    print(f"Reports: {json_path} and {markdown_path}")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT_DIR / "data/raw/PlantVillage")
    parser.add_argument(
        "--mapping",
        type=Path,
        default=ROOT_DIR / "data/metadata/plantvillage_class_mapping.csv",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=ROOT_DIR / "models/plant_disease_cnn.pth",
    )
    parser.add_argument("--reports-dir", type=Path, default=ROOT_DIR / "reports")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    evaluate(args.data_dir, args.mapping, args.checkpoint, args.reports_dir, args.seed)


if __name__ == "__main__":
    main()