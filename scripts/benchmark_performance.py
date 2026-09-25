"""
Performance Benchmarking Script for Plant Disease Detection & Advisory Pipeline.

Measures:
  1. Image preprocessing time (validation, resize, normalization, tensor conversion)
  2. Vision CNN inference time (CPU / GPU forward pass & embedding extraction)
  3. RAG Knowledge Base retrieval time (vector search & document mapping)
  4. Advisory generation time (grounding verification, evidence chunking, message synthesis)
  5. Total End-to-End Pipeline Response Time

Generates summary latency tables and reports preparation for Week 8 optimization.
"""

import os
import sys
import time
import json
import statistics
from typing import Dict, Any, List
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.pipeline import PlantDiseasePipeline
from src.preprocessing.pipeline import PreprocessingPipeline
from src.vision.classifier import PlantDiseaseClassifier
from src.retrieval.rag_retriever import RAGRetriever
from src.advisory.advisory_generator import AdvisoryGenerator
from src.contracts import VisionPrediction, PredictionStatus


def run_benchmarks(num_warmup: int = 10, num_iterations: int = 100) -> Dict[str, Any]:
    print("=" * 70)
    print("PLANT DISEASE DETECTION & ADVISORY SYSTEM — PERFORMANCE BENCHMARK")
    print(f"Date: 25 September 2026 | Warmup: {num_warmup} | Iterations: {num_iterations}")
    print("=" * 70)

    # 1. Initialize components
    pipeline = PlantDiseasePipeline()
    prep = PreprocessingPipeline(target_size=(224, 224))
    classifier = pipeline.classifier
    retriever = pipeline.retriever
    generator = pipeline.generator

    # Create synthetic test leaf
    leaf_arr = np.zeros((224, 224, 3), dtype=np.uint8)
    leaf_arr[:, :, 1] = 175
    leaf_arr[:, :, 0] = 35

    # ── Warmup Phase ────────────────────────────────────────────────────────
    print("\nWarming up pipeline components...")
    for _ in range(num_warmup):
        _ = pipeline.predict_and_advise(leaf_arr)

    # ── 1. Image Preprocessing Benchmark ──────────────────────────────────
    print("Benchmarking Preprocessing...")
    prep_times: List[float] = []
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        _is_valid, _tensor, _meta = prep.process_image(leaf_arr, return_tensor=True)
        t1 = time.perf_counter()
        prep_times.append((t1 - t0) * 1000.0)

    # ── 2. Vision CNN Inference Benchmark ─────────────────────────────────
    print("Benchmarking Vision CNN Inference...")
    _, tensor_data, _ = prep.process_image(leaf_arr, return_tensor=True)
    vision_times: List[float] = []
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        _ = classifier.predict(leaf_arr, extract_embedding=True)
        t1 = time.perf_counter()
        vision_times.append((t1 - t0) * 1000.0)

    # ── 3. RAG Retrieval Benchmark ────────────────────────────────────────
    print("Benchmarking RAG Retrieval...")
    test_prediction = VisionPrediction(
        plant="Tomato",
        disease="Early blight",
        canonical_id="tomato_early_blight",
        confidence=0.91,
        status=PredictionStatus.SUPPORTED.value
    )
    retrieval_times: List[float] = []
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        _advisory = retriever.retrieve(test_prediction.canonical_id)
        t1 = time.perf_counter()
        retrieval_times.append((t1 - t0) * 1000.0)

    # ── 4. Advisory Generation Benchmark ──────────────────────────────────
    print("Benchmarking Advisory Generation...")
    advisory_times: List[float] = []
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        _response = generator.generate_advisory(test_prediction)
        t1 = time.perf_counter()
        advisory_times.append((t1 - t0) * 1000.0)

    # ── 5. Full End-to-End Pipeline Benchmark ─────────────────────────────
    print("Benchmarking Full End-to-End Pipeline...")
    e2e_times: List[float] = []
    for _ in range(num_iterations):
        t0 = time.perf_counter()
        _res = pipeline.predict_and_advise(leaf_arr)
        t1 = time.perf_counter()
        e2e_times.append((t1 - t0) * 1000.0)

    def stats_summary(times: List[float]) -> Dict[str, float]:
        sorted_times = sorted(times)
        p95_idx = int(0.95 * len(sorted_times))
        return {
            "mean_ms": round(statistics.mean(times), 3),
            "median_ms": round(statistics.median(times), 3),
            "min_ms": round(min(times), 3),
            "max_ms": round(max(times), 3),
            "p95_ms": round(sorted_times[p95_idx], 3),
            "std_ms": round(statistics.stdev(times), 3) if len(times) > 1 else 0.0
        }

    results = {
        "device": str(classifier.device),
        "num_iterations": num_iterations,
        "preprocessing": stats_summary(prep_times),
        "vision_inference": stats_summary(vision_times),
        "rag_retrieval": stats_summary(retrieval_times),
        "advisory_generation": stats_summary(advisory_times),
        "end_to_end_total": stats_summary(e2e_times),
        "throughput_fps": round(1000.0 / statistics.mean(e2e_times), 1)
    }

    # Print Formatted Report
    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS SUMMARY (Device: " + results["device"].upper() + ")")
    print("=" * 70)
    header = f"{'Pipeline Stage':<26} | {'Mean (ms)':<10} | {'Median (ms)':<11} | {'P95 (ms)':<9} | {'Min/Max (ms)':<14}"
    print(header)
    print("-" * len(header))

    stages = [
        ("1. Preprocessing", "preprocessing"),
        ("2. Vision Inference", "vision_inference"),
        ("3. RAG Retrieval", "rag_retrieval"),
        ("4. Advisory Generation", "advisory_generation"),
        ("5. End-to-End Total", "end_to_end_total")
    ]

    for label, key in stages:
        s = results[key]
        min_max = f"{s['min_ms']:.1f}/{s['max_ms']:.1f}"
        print(f"{label:<26} | {s['mean_ms']:<10.3f} | {s['median_ms']:<11.3f} | {s['p95_ms']:<9.3f} | {min_max:<14}")

    print("-" * len(header))
    print(f"End-to-End Throughput: {results['throughput_fps']} inferences / second (FPS)")
    print("=" * 70)

    # Save benchmark report to reports directory
    os.makedirs("reports", exist_ok=True)
    report_path = "reports/benchmark_report.json"
    with open(report_path, mode="w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nDetailed JSON report saved to: {report_path}")

    return results


if __name__ == "__main__":
    run_benchmarks(num_warmup=10, num_iterations=100)
