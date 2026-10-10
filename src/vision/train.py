"""
Train the PlantDiseaseCNN from the extracted PlantVillage class folders.

The dataset is read from data/raw/PlantVillage/<original_label>/*.jpg.
Class IDs come from data/metadata/plantvillage_class_mapping.csv; missing
classes are excluded and recorded in the checkpoint instead of being assigned
random labels.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union, TYPE_CHECKING

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if TYPE_CHECKING:
    from torch.utils.data import Dataset, DataLoader
    import torch
    import torch.nn as nn
    from src.vision.model import PlantDiseaseCNN
    HAS_TORCH: bool = True
else:
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, Dataset
        HAS_TORCH = True
    except ImportError:
        torch = None
        nn = None
        DataLoader = None
        Dataset = object
        HAS_TORCH = False

    if HAS_TORCH:
        from src.vision.model import PlantDiseaseCNN
    else:
        PlantDiseaseCNN = None

try:
    import numpy as np
except ImportError:
    np = None
try:
    from PIL import Image
except ImportError:
    Image = None

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


try:
    import torchvision.transforms as transforms
    HAS_TORCHVISION = True
except ImportError:
    transforms = None
    HAS_TORCHVISION = False

from src.dataset_index import (
    NOT_A_PLANT_LABEL,
    discover_class_images,
    load_class_mapping,
    not_a_plant_class_id,
    split_images,
)

class LeafImageDataset(Dataset):
    def __init__(self, records: Sequence[Tuple[Path, int]], augment: bool = False):
        self.records = list(records)
        self.augment = augment
        if HAS_TORCHVISION and transforms is not None:
            if augment:
                self.transform = transforms.Compose([
                    transforms.Resize((224, 224), interpolation=transforms.InterpolationMode.BILINEAR),
                    transforms.RandomHorizontalFlip(),
                    transforms.RandomVerticalFlip(),
                    transforms.RandomRotation(15),
                    transforms.ColorJitter(brightness=0.1, contrast=0.1),
                    transforms.ToTensor(),
                    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
                ])
            else:
                self.transform = transforms.Compose([
                    transforms.Resize((224, 224), interpolation=transforms.InterpolationMode.BILINEAR),
                    transforms.ToTensor(),
                    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
                ])
            self.transformer = None
        else:
            self.transform = None
            from src.preprocessing.image_transforms import ImageTransformer
            self.transformer = ImageTransformer(target_size=(224, 224), augment=augment)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int):
        path, class_index = self.records[index]
        try:
            with Image.open(path) as source:
                image = source.convert("RGB")
            if self.transform is not None:
                tensor = self.transform(image)
            else:
                array = self.transformer.transform(image, return_tensor=False)
                tensor = torch.from_numpy(np.asarray(array, dtype=np.float32).copy())
        except Exception as error:
            raise RuntimeError(f"Could not load training image {path}: {error}") from error

        return tensor, class_index


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def evaluate(
    model,
    loader,
    criterion,
    device,
    class_count: int,
) -> Dict[str, float]:
    model.eval()
    total_loss = 0.0
    total = 0
    correct = 0
    per_class_correct = [0] * class_count
    per_class_total = [0] * class_count

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            logits, _ = model(images)
            loss = criterion(logits, labels)
            predictions = logits.argmax(dim=1)

            batch_size = labels.size(0)
            total_loss += float(loss.item()) * batch_size
            total += batch_size
            correct += int((predictions == labels).sum().item())
            for label, prediction in zip(labels.tolist(), predictions.tolist()):
                per_class_total[label] += 1
                if label == prediction:
                    per_class_correct[label] += 1

    class_accuracies = [
        per_class_correct[index] / per_class_total[index]
        for index in range(class_count)
        if per_class_total[index] > 0
    ]
    return {
        "loss": total_loss / max(total, 1),
        "accuracy": correct / max(total, 1),
        "macro_accuracy": sum(class_accuracies) / max(len(class_accuracies), 1),
    }


def train_model(
    epochs: int = 15,
    batch_size: int = 32,
    learning_rate: float = 1e-3,
    save_path: str = "models/plant_disease_cnn.pth",
    data_dir: str = "data/raw/PlantVillage",
    mapping_path: str = "data/metadata/plantvillage_class_mapping.csv",
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    patience: int = 5,
    seed: int = 42,
    max_images_per_class: Optional[int] = None,
    device: Optional[str] = None,
    num_workers: int = 0,
    init_from: Optional[str] = None,
    report_path: str = "reports/training_report.json",
) -> Dict[str, Any]:
    missing_dependencies = []
    if not HAS_TORCH:
        missing_dependencies.append("torch")
    if np is None:
        missing_dependencies.append("numpy")
    if Image is None:
        missing_dependencies.append("Pillow")
    if missing_dependencies:
        return {
            "status": "skipped",
            "message": (
                "Missing image-training dependencies: "
                + ", ".join(missing_dependencies)
                + ". Install NumPy and Pillow with: "
                + ".venv\\Scripts\\python.exe -m pip install numpy pillow; install PyTorch from https://pytorch.org/get-started/locally/ for Windows/GPU."
            ),
        }
    if epochs < 1 or batch_size < 2:
        raise ValueError("epochs must be >= 1 and batch_size must be >= 2.")
    if num_workers < 0:
        raise ValueError("num_workers must be >= 0.")

    set_seed(seed)
    mapping_file = Path(mapping_path)
    if not mapping_file.is_absolute():
        mapping_file = ROOT_DIR / mapping_file
    image_root = Path(data_dir)
    if not image_root.is_absolute():
        image_root = ROOT_DIR / image_root

    mapping = load_class_mapping(mapping_file)
    reject_id = not_a_plant_class_id(mapping)
    class_ids, images_by_id, missing_classes = discover_class_images(
        image_root, mapping, max_images_per_class=max_images_per_class,
        include_not_a_plant=True,
    )
    has_reject_class = reject_id in class_ids
    train_records, val_records, test_records = split_images(
        class_ids, images_by_id, val_ratio, test_ratio, seed
    )
    class_index_by_id = {class_id: index for index, class_id in enumerate(class_ids)}
    remap = lambda records: [
        (path, class_index_by_id[class_id]) for path, class_id in records
    ]

    train_dataset = LeafImageDataset(remap(train_records), augment=True)
    val_dataset = LeafImageDataset(remap(val_records), augment=False)
    test_dataset = LeafImageDataset(remap(test_records), augment=False)

    device_obj = torch.device(
        device if device else ("cuda" if torch.cuda.is_available() else "cpu")
    )
    loader_options = {
        "batch_size": batch_size,
        "num_workers": num_workers,
        "pin_memory": device_obj.type == "cuda",
    }
    worker_options = (
        {"persistent_workers": True, "prefetch_factor": 2}
        if num_workers > 0 else {}
    )
    drop_last = len(train_dataset) > batch_size and len(train_dataset) % batch_size == 1
    train_loader = DataLoader(
        train_dataset, shuffle=True, drop_last=drop_last, **loader_options, **worker_options
    )
    val_loader = DataLoader(val_dataset, shuffle=False, **loader_options, **worker_options)
    test_loader = DataLoader(test_dataset, shuffle=False, **loader_options, **worker_options)

    counts = [sum(label == class_id for _, label in train_records) for class_id in class_ids]
    weights = torch.tensor(
        [len(train_records) / (len(class_ids) * count) for count in counts],
        dtype=torch.float32,
        device=device_obj,
    )
    weights = torch.clamp(weights, max=5.0)
    if has_reject_class and len(class_ids) > 1:
        # Inverse-frequency weight (~ (disease_images / n_disease_classes) / reject_images)
        # for the small Not_a_plant class, capped at 10x the mean disease-class weight.
        reject_index = class_ids.index(reject_id)
        disease_mask = torch.ones(len(class_ids), dtype=torch.bool, device=device_obj)
        disease_mask[reject_index] = False
        disease_mean = weights[disease_mask].mean()
        weights[reject_index] = torch.minimum(weights[reject_index], 10.0 * disease_mean)
    weights = weights / weights.mean()

    model = PlantDiseaseCNN(num_classes=len(class_ids), embedding_dim=128).to(device_obj)
    if init_from:
        initial_path = Path(init_from)
        if not initial_path.is_absolute():
            initial_path = ROOT_DIR / initial_path
        initial_checkpoint = torch.load(initial_path, map_location="cpu")
        initial_state = (
            initial_checkpoint.get("state_dict", initial_checkpoint)
            if isinstance(initial_checkpoint, dict) else initial_checkpoint
        )
        if not isinstance(initial_state, dict):
            raise ValueError(f"Initial checkpoint is invalid: {initial_path}")
        # Keep learned leaf features and plant class weights, while adding the
        # new non-plant output as an additional class.
        compatible_state = {
            key: value for key, value in initial_state.items()
            if key in model.state_dict() and model.state_dict()[key].shape == value.shape
            and not key.startswith("classifier.")
        }
        model.load_state_dict(compatible_state, strict=False)
        previous_ids = (
            [int(class_id) for class_id in initial_checkpoint.get("class_ids", [])]
            if isinstance(initial_checkpoint, dict) else []
        )
        previous_positions = {class_id: index for index, class_id in enumerate(previous_ids)}
        source_weight = initial_state.get("classifier.weight")
        source_bias = initial_state.get("classifier.bias")
        if source_weight is not None and source_bias is not None:
            with torch.no_grad():
                model.classifier.weight.normal_(mean=0.0, std=0.02)
                model.classifier.bias.zero_()
                for target_index, class_id in enumerate(class_ids):
                    source_index = previous_positions.get(class_id)
                    if source_index is not None and source_index < source_weight.shape[0]:
                        model.classifier.weight[target_index].copy_(source_weight[source_index])
                        model.classifier.bias[target_index].copy_(source_bias[source_index])
        print(f"Initialized from existing checkpoint {initial_path}")
    criterion = nn.CrossEntropyLoss(weight=weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=2
    )

    output_path = Path(save_path)
    if not output_path.is_absolute():
        output_path = ROOT_DIR / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    best_state = None
    best_macro_accuracy = -1.0
    best_val_accuracy = 0.0
    best_val_loss = float("inf")
    epochs_without_improvement = 0
    history: List[Dict[str, float]] = []

    print(f"Training from {image_root}")
    print(
        f"Using {len(class_ids)}/{len(mapping)} classes and "
        f"{len(train_records)} train, {len(val_records)} validation, "
        f"{len(test_records)} test images on {device_obj}."
    )
    if missing_classes:
        print("Classes without images (not trainable): " + ", ".join(missing_classes))

    for epoch in range(epochs):
        model.train()
        running_loss = 0.0
        total = 0
        correct = 0

        for images, labels in train_loader:
            images = images.to(device_obj, non_blocking=True)
            labels = labels.to(device_obj, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            logits, _ = model(images)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()

            count = labels.size(0)
            running_loss += float(loss.item()) * count
            total += count
            correct += int((logits.argmax(dim=1) == labels).sum().item())

        train_metrics = {
            "loss": running_loss / max(total, 1),
            "accuracy": correct / max(total, 1),
        }
        val_metrics = evaluate(
            model, val_loader, criterion, device_obj, class_count=len(class_ids)
        )
        scheduler.step(val_metrics["loss"])
        epoch_metrics = {
            "epoch": float(epoch + 1),
            "train_loss": train_metrics["loss"],
            "train_accuracy": train_metrics["accuracy"],
            "val_loss": val_metrics["loss"],
            "val_accuracy": val_metrics["accuracy"],
            "val_macro_accuracy": val_metrics["macro_accuracy"],
        }
        history.append(epoch_metrics)
        print(
            f"Epoch {epoch + 1}/{epochs}: "
            f"train_loss={train_metrics['loss']:.4f}, "
            f"val_loss={val_metrics['loss']:.4f}, "
            f"val_accuracy={val_metrics['accuracy']:.3f}, "
            f"val_macro_accuracy={val_metrics['macro_accuracy']:.3f}"
        )

        improved = (
            val_metrics["macro_accuracy"] > best_macro_accuracy
            or (
                val_metrics["macro_accuracy"] == best_macro_accuracy
                and val_metrics["loss"] < best_val_loss
            )
        )
        if improved:
            best_macro_accuracy = val_metrics["macro_accuracy"]
            best_val_accuracy = val_metrics["accuracy"]
            best_val_loss = val_metrics["loss"]
            best_state = {
                key: value.detach().cpu().clone()
                for key, value in model.state_dict().items()
            }
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= patience:
                print(f"Early stopping after {epoch + 1} epochs.")
                break

    if best_state is None:
        raise RuntimeError("Training did not produce a usable checkpoint.")
    model.load_state_dict(best_state)
    model.to(device_obj)
    test_metrics = evaluate(
        model, test_loader, criterion, device_obj, class_count=len(class_ids)
    )

    checkpoint = {
        "model_version": "vision_image_trained_v2",
        "trained_on_images": True,
        "num_classes": len(class_ids),
        "class_ids": class_ids,
        "class_labels": [
            mapping[class_id]["original_label"] if class_id in mapping else NOT_A_PLANT_LABEL
            for class_id in class_ids
        ],
        "not_a_plant_class_id": reject_id if has_reject_class else None,
        "embedding_dim": 128,
        "state_dict": best_state,
        "final_acc": best_macro_accuracy,
        "val_accuracy": best_val_accuracy,
        "val_macro_accuracy": best_macro_accuracy,
        "test_accuracy": test_metrics["accuracy"],
        "test_macro_accuracy": test_metrics["macro_accuracy"],
        "image_counts": {
            str(class_id): len(images_by_id[class_id]) for class_id in class_ids
        },
        "split_counts": {
            "train": len(train_records),
            "val": len(val_records),
            "test": len(test_records),
        },
        "missing_classes": missing_classes,
        "history": history,
        "seed": seed,
    }
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    torch.save(checkpoint, temporary_path)
    os.replace(temporary_path, output_path)

    report_output_path = Path(report_path)
    if not report_output_path.is_absolute():
        report_output_path = ROOT_DIR / report_output_path
    report_output_path.parent.mkdir(parents=True, exist_ok=True)
    report = {key: value for key, value in checkpoint.items() if key != "state_dict"}
    report["checkpoint_path"] = str(output_path)
    report_output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Training report saved to {report_output_path}")

    print(f"Checkpoint saved to {output_path}")
    print(
        f"Test accuracy: {test_metrics['accuracy']:.3f}; "
        f"test macro accuracy: {test_metrics['macro_accuracy']:.3f}"
    )
    return {
        "status": "success",
        "save_path": str(output_path),
        "num_classes": len(class_ids),
        "missing_classes": missing_classes,
        "val_macro_accuracy": best_macro_accuracy,
        "test_accuracy": test_metrics["accuracy"],
        "test_macro_accuracy": test_metrics["macro_accuracy"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train PlantDiseaseCNN on the extracted PlantVillage image folders."
    )
    parser.add_argument("--epochs", type=int, default=15)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--num-workers", type=int, default=0, help="Parallel image-loading workers; 0 for Windows.")
    parser.add_argument("--learning-rate", type=float, default=1e-3)
    parser.add_argument("--data-dir", default="data/raw/PlantVillage")
    parser.add_argument(
        "--mapping", default="data/metadata/plantvillage_class_mapping.csv"
    )
    parser.add_argument("--output", default="models/plant_disease_cnn.pth")
    parser.add_argument("--init-from", default=None, help="Optional checkpoint to fine-tune while adding classes.")
    parser.add_argument("--report", default="reports/training_report.json")
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--max-images-per-class",
        type=int,
        default=None,
        help="Optional cap per class for a quick trial; omit for full training.",
    )
    parser.add_argument("--device", default=None, help="Optional torch device, e.g. cpu or cuda")
    args = parser.parse_args()

    result = train_model(
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        save_path=args.output,
        data_dir=args.data_dir,
        mapping_path=args.mapping,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        patience=args.patience,
        seed=args.seed,
        max_images_per_class=args.max_images_per_class,
        device=args.device,
        num_workers=args.num_workers,
        init_from=args.init_from,
        report_path=args.report,
    )
    if result["status"] != "success":
        raise SystemExit(result.get("message", "Training did not complete."))


if __name__ == "__main__":
    main()
