# Final Testing & Evaluation Procedure (Standard Operating Procedure)

> **Milestone**: Sprint 10 Deliverable — Finalized Testing Procedure  
> **Applicability**: Unseen dataset final evaluation, baseline regression testing, and production deployment audit.

---

## 1. Scope and Prerequisites

This procedure outlines the exact steps to evaluate both the baseline 38-class system and the rapidly adapted unseen-dataset pipeline.

### Prerequisites:
- Python 3.10+ virtual environment (`.venv\Scripts\python.exe`)
- Model weights: `models/plant_disease_cnn.pth`
- Vector Store Index: `models/vector_index/`
- Agricultural Knowledge Base: `data/knowledge_base/agricultural_documents.json`

---

## 2. Standard Testing Steps

### Step 1: Baseline Freeze & Integrity Check
Before running any unseen evaluation, assert that the frozen baseline components have not undergone unauthorized alterations.

```bash
# Verify cryptographic hashes against frozen baseline manifest
python -c "from src.adaptation.baseline_freeze import BaselineFreezer; freezer = BaselineFreezer(); valid, mismatches = freezer.verify_integrity(); print('Integrity OK' if valid else mismatches); exit(0 if valid else 1)"
```

### Step 2: Automated Unit & Scenario Regression Tests
Ensure all 138 unit, integration, and scenario tests pass cleanly.

```bash
# Execute full test discovery suite
python -m unittest discover -s tests -p "test_*.py"
```

Expected output: `Ran 138 tests ... OK`

### Step 3: Run Baseline Known-Dataset Evaluation
Execute quantitative metric evaluation across the 38 canonical classes.

```bash
python scripts/evaluate_known_dataset.py
```

Outputs produced:
- `reports/baseline_evaluation_report.json`
- `reports/baseline_evaluation_report.md`

### Step 4: Run CPU Inference Latency Benchmarking
Benchmark the end-to-end processing pipeline across 100 sample iterations.

```bash
python scripts/benchmark_performance.py
```

Outputs produced:
- `reports/benchmark_report.json`

### Step 5: Execute Unseen Dataset Rapid Adaptation
Ingest unseen crop support sets, register visual prototype centroids, update the RAG vector store, and evaluate query predictions.

```bash
python scripts/adapt_unseen_dataset.py
```

Outputs produced:
- `reports/unseen_adaptation_results.json`
- `reports/unseen_adaptation_report.md`

---

## 3. Evaluation Acceptance Criteria

| Criteria | Target Threshold | Validation Script |
| :--- | :--- | :--- |
| **Integrity Check** | Zero Hash Mismatches | `src/adaptation/baseline_freeze.py` |
| **Unit Test Suite** | $138 / 138$ (100% Passing) | `unittest discover` |
| **End-to-End CPU Latency** | $< 35\text{ ms / image}$ | `scripts/benchmark_performance.py` |
| **Known-Data Top-1 Accuracy** | $\ge 85\%$ | `scripts/evaluate_known_dataset.py` |
| **Unseen Adaptation Accuracy** | $\ge 80\%$ (5-shot prototype) | `scripts/adapt_unseen_dataset.py` |
| **Grounding Verification** | Actionable Prevention & Management | `src/retrieval/rag_retriever.py` |
