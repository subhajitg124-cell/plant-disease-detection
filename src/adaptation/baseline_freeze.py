"""
Baseline Pipeline Freezer & Integrity Manifest Manager.
Used for Sprint 10 to lock the baseline architecture, checkpoints, and RAG knowledge
prior to unseen evaluation.
"""

import os
import sys
import json
import hashlib
import time
from typing import Dict, Any, List, Optional, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


class BaselineFreezer:
    """Manages baseline model freezing, checksum generation, and integrity verification."""

    DEFAULT_FILES_TO_FREEZE = [
        "models/plant_disease_cnn.pth",
        "data/knowledge_base/agricultural_documents.json",
        "models/vector_index/vector_documents.json",
        "models/vector_index/canonical_index.json",
        "src/contracts.py",
        "src/pipeline.py",
        "src/vision/classifier.py",
        "src/retrieval/rag_retriever.py",
        "src/advisory/advisory_generator.py"
    ]

    def __init__(self, manifest_path: str = "reports/baseline_freeze_manifest.json"):
        self.manifest_path = manifest_path

    @staticmethod
    def compute_sha256(file_path: str) -> str:
        """Computes hex SHA-256 hash for a given file."""
        if not os.path.exists(file_path):
            return "FILE_NOT_FOUND"
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha.update(chunk)
        return sha.hexdigest()

    def generate_freeze_manifest(
        self,
        files_to_freeze: Optional[List[str]] = None,
        notes: str = "Baseline frozen for unseen dataset evaluation"
    ) -> Dict[str, Any]:
        """Generates and writes a cryptographic integrity manifest."""
        target_files = files_to_freeze or self.DEFAULT_FILES_TO_FREEZE
        file_manifest: Dict[str, Dict[str, Any]] = {}

        for fpath in target_files:
            exists = os.path.exists(fpath)
            size_bytes = os.path.getsize(fpath) if exists else 0
            file_manifest[fpath] = {
                "exists": exists,
                "size_bytes": size_bytes,
                "sha256": self.compute_sha256(fpath)
            }

        manifest = {
            "baseline_version": "1.0.0-frozen-baseline",
            "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "notes": notes,
            "hyperparameters": {
                "input_resolution": [224, 224],
                "confidence_threshold": 0.60,
                "foliage_greenness_threshold": 0.05,
                "embedding_dimension": 128,
                "vector_store_dimension": 256,
                "num_canonical_classes": 38
            },
            "components": file_manifest
        }

        os.makedirs(os.path.dirname(self.manifest_path), exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return manifest

    def verify_integrity(self) -> Tuple[bool, List[str]]:
        """Verifies current codebase against the frozen manifest."""
        if not os.path.exists(self.manifest_path):
            return False, [f"Manifest file not found: {self.manifest_path}"]

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        mismatches: List[str] = []
        components = manifest.get("components", {})

        for fpath, meta in components.items():
            current_hash = self.compute_sha256(fpath)
            expected_hash = meta.get("sha256")
            if current_hash != expected_hash:
                mismatches.append(
                    f"Integrity mismatch in '{fpath}': Expected {expected_hash}, got {current_hash}"
                )

        return (len(mismatches) == 0), mismatches


if __name__ == "__main__":
    freezer = BaselineFreezer()
    manifest = freezer.generate_freeze_manifest()
    print("Baseline Freeze Manifest created successfully:")
    print(json.dumps(manifest, indent=2))
