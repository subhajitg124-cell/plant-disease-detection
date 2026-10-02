import os
import sys

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import csv
from typing import Any, Dict, List, Optional, Union
import numpy as np
from PIL import Image

try:
    import torch
    import torch.nn.functional as F
    HAS_TORCH = True
except ImportError:
    torch = None
    F = None
    HAS_TORCH = False

from src.contracts import VisionPrediction, PredictionStatus

if HAS_TORCH:
    try:
        from src.vision.model import PlantDiseaseCNN
    except ImportError:
        from model import PlantDiseaseCNN
else:
    PlantDiseaseCNN = None

try:
    from src.preprocessing.pipeline import PreprocessingPipeline
except ImportError:
    from preprocessing.pipeline import PreprocessingPipeline


class PlantDiseaseClassifier:
    def __init__(
        self,
        model_path: Optional[str] = "models/plant_disease_cnn.pth",
        class_mapping_path: str = "data/metadata/plantvillage_class_mapping.csv",
        confidence_threshold: float = 0.60,
        device: Optional[str] = None
    ):
        self.model_path = model_path
        self.class_mapping_path = class_mapping_path
        self.confidence_threshold = confidence_threshold
        self.model_is_reliable = False
        self.checkpoint_loaded = False
        self.trained_on_images = False
        self.checkpoint_metadata: Dict[str, Any] = {}

        if HAS_TORCH:
            if device is None:
                self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            else:
                self.device = torch.device(device)
        else:
            self.device = "cpu"

        self.class_map = self._load_class_mapping()
        self.model_class_ids = sorted(self.class_map)
        self.active_class_ids: List[int] = []
        self.num_classes = max(len(self.class_map), 38)
        self.pipeline = PreprocessingPipeline(target_size=(224, 224))
        self.model = None
        self._init_model()

    def _load_class_mapping(self) -> Dict[int, Dict[str, str]]:
        mapping: Dict[int, Dict[str, str]] = {}
        if os.path.exists(self.class_mapping_path):
            with open(self.class_mapping_path, mode="r", encoding="utf-8-sig") as handle:
                for row in csv.DictReader(handle):
                    class_id = int(row["class_id"])
                    mapping[class_id] = {
                        "canonical_id": row["canonical_id"],
                        "plant": row["plant"],
                        "disease": row["disease"],
                        "original_label": row.get("original_label", "")
                    }
        else:
            for class_id in range(38):
                mapping[class_id] = {
                    "canonical_id": f"plant_disease_{class_id}",
                    "plant": "Plant",
                    "disease": f"Disease_{class_id}",
                    "original_label": f"Class_{class_id}"
                }
        return mapping

    def _init_model(self) -> None:
        if not HAS_TORCH:
            return

        checkpoint = None
        state_dict = None
        class_ids = sorted(self.class_map)
        if self.model_path and os.path.exists(self.model_path):
            try:
                checkpoint = torch.load(self.model_path, map_location=self.device)
                state_dict = (
                    checkpoint.get("state_dict", checkpoint)
                    if isinstance(checkpoint, dict)
                    else checkpoint
                )
                if not isinstance(state_dict, dict):
                    raise ValueError("Checkpoint does not contain a valid state_dict.")

                saved_ids = checkpoint.get("class_ids") if isinstance(checkpoint, dict) else None
                if saved_ids is not None:
                    class_ids = [int(class_id) for class_id in saved_ids]
                output_count = int(state_dict["classifier.weight"].shape[0])
                if len(class_ids) != output_count:
                    if saved_ids is None and output_count == len(self.class_map):
                        class_ids = sorted(self.class_map)
                    else:
                        raise ValueError(
                            "Checkpoint class_ids do not match its classifier output size."
                        )
                unknown_ids = [
                    class_id for class_id in class_ids if class_id not in self.class_map
                ]
                if unknown_ids:
                    raise ValueError(f"Checkpoint references unmapped class IDs: {unknown_ids}")

                self.model = PlantDiseaseCNN(num_classes=output_count).to(self.device)
                self.model.load_state_dict(state_dict)
                self.model_class_ids = class_ids
                self.num_classes = output_count
                self.checkpoint_metadata = checkpoint if isinstance(checkpoint, dict) else {}
                self.checkpoint_loaded = True
                self.trained_on_images = bool(
                    self.checkpoint_metadata.get("trained_on_images", False)
                )
                self.active_class_ids = list(class_ids) if self.trained_on_images else []

                score = float(
                    self.checkpoint_metadata.get(
                        "val_macro_accuracy",
                        self.checkpoint_metadata.get("final_acc", 0.0)
                    )
                )
                quality_floor = max(0.15, 2.0 / max(len(class_ids), 1))
                self.model_is_reliable = (
                    self.trained_on_images and score >= quality_floor
                )
                if not self.trained_on_images:
                    print(
                        "[WARNING] Checkpoint is not marked as trained on real images; "
                        "predictions are disabled."
                    )
                elif not self.model_is_reliable:
                    print(
                        f"[WARNING] Validation macro accuracy {score:.1%} is below "
                        f"the {quality_floor:.1%} quality floor."
                    )
            except Exception as error:
                print(
                    f"Warning: Failed to load checkpoint '{self.model_path}': {error}. "
                    "Predictions are disabled."
                )
                self.model = None
                self.checkpoint_loaded = False
                self.trained_on_images = False
                self.model_is_reliable = False
                self.checkpoint_metadata = {}
                self.model_class_ids = sorted(self.class_map)
                self.active_class_ids = []
                self.num_classes = max(len(self.class_map), 38)

        if self.model is None:
            self.model = PlantDiseaseCNN(num_classes=self.num_classes).to(self.device)
        self.model.eval()

    def _unknown_prediction(self, message: str) -> VisionPrediction:
        return VisionPrediction(
            plant="Unknown",
            disease=message,
            canonical_id="model_not_ready",
            confidence=0.0,
            status=PredictionStatus.UNKNOWN.value,
            raw_label="model_not_ready",
            embedding=None,
            model_version=str(
                self.checkpoint_metadata.get("model_version", "untrained")
            ),
        )

    def predict(
        self,
        input_source: Union[str, Image.Image, np.ndarray, Any],
        extract_embedding: bool = True,
        plant_hint: str = ""
    ) -> VisionPrediction:
        is_valid, data, meta = self.pipeline.process_image(input_source, return_tensor=True)
        if not is_valid or meta.get("status") == PredictionStatus.NOT_A_PLANT.value:
            return VisionPrediction(
                plant="Non-Plant / Corrupted",
                disease="Invalid Image",
                canonical_id="not_a_plant",
                confidence=0.0,
                status=PredictionStatus.NOT_A_PLANT.value,
                raw_label="not_a_plant",
                embedding=None,
                model_version="vision_v1"
            )

        if not self.trained_on_images or self.model is None or not HAS_TORCH:
            return self._unknown_prediction(
                "No real-image trained model checkpoint is available."
            )

        if not isinstance(data, torch.Tensor):
            return self._unknown_prediction("The model could not prepare this image.")

        if data.ndim == 3:
            data = data.unsqueeze(0)
        data = data.to(self.device)

        with torch.no_grad():
            logits, embedding = self.model(data)
            probabilities = F.softmax(logits, dim=1)[0]
            top_index = int(torch.argmax(probabilities).item())
            confidence = float(probabilities[top_index].item())
            embedding_list = (
                embedding[0].detach().cpu().tolist() if extract_embedding else None
            )

        if top_index >= len(self.model_class_ids):
            return self._unknown_prediction("The checkpoint class mapping is invalid.")

        class_id = self.model_class_ids[top_index]
        class_info = self.class_map.get(class_id)
        if class_info is None or class_id not in self.active_class_ids:
            return self._unknown_prediction("The predicted class is not in this checkpoint.")

        status = (
            PredictionStatus.SUPPORTED.value
            if self.model_is_reliable and confidence >= self.confidence_threshold
            else PredictionStatus.UNCERTAIN.value
        )
        return VisionPrediction(
            plant=class_info["plant"],
            disease=class_info["disease"],
            canonical_id=class_info["canonical_id"],
            confidence=confidence,
            status=status,
            raw_label=class_info.get("original_label"),
            embedding=embedding_list,
            model_version=str(
                self.checkpoint_metadata.get("model_version", "vision_image_trained_v2")
            )
        )