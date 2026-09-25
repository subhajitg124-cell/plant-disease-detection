# Plant Disease Detection & Advisory System

> **Status**: **Phase 3 & 4 (September Milestones) — Fully Integrated End-to-End Vision + RAG Advisory Pipeline** (`[VERIFIED & PASSING]`)  
> **Milestone Date**: 25 September 2026 | **133/133 Unit & Integration Tests Passing**

---

## 1. Project Overview

**Plant Disease Detection & Advisory System** is an AI-driven agricultural diagnostics and decision-support platform. By tightly coupling **Computer Vision (CNN)**, **Canonical Plant Disease Taxonomies**, **Domain-Structured Semantic Vector Indexing (RAG)**, and **Authoritative Agricultural Extension Knowledge Bases**, the system delivers evidence-grounded plant pathology diagnostics, causes, risk factors, prevention strategies, and treatment protocols directly to growers, agronomists, and agricultural extension agents.

---

## 2. End-to-End Pipeline Architecture

```
                                  [ Input Leaf Image ]
                                           │
                                           ▼
                       ┌───────────────────────────────────────┐
                       │   1. Preprocessing & Plant Validator  │
                       │   - Integrity & dimension checks      │
                       │   - HSV Foliage ratio gating (>5%)    │
                       └───────────────────┬───────────────────┘
                                           │
                        [ Valid Plant Image (224x224x3) ]
                                           │
                                           ▼
                       ┌───────────────────────────────────────┐
                       │     2. Vision CNN Classifier Engine   │
                       │   - 4-Block Conv2D + BatchNorm + GAP  │
                       │   - 128-dim Visual Embedding Head     │
                       │   - 38 PlantVillage Disease Classes   │
                       └───────────────────┬───────────────────┘
                                           │
                         [ VisionPrediction (Data Contract) ]
                         - plant, disease, canonical_id
                         - confidence score & status gating
                                           │
                                           ▼
                       ┌───────────────────────────────────────┐
                       │     3. RAG Knowledge Base Retriever   │
                       │   - Exact Canonical ID lookup (O(1))  │
                       │   - 256-dim Semantic Vector Search    │
                       │   - 38 Structured Extension Documents │
                       └───────────────────┬───────────────────┘
                                           │
                         [ AdvisoryResult (Data Contract) ]
                         - symptoms, causes, risk factors
                         - prevention, management, sources
                                           │
                                           ▼
                       ┌───────────────────────────────────────┐
                       │     4. Advisory Generator Engine      │
                       │   - Safety & Confidence gating        │
                       │   - Evidence chunk extraction         │
                       │   - Grounded diagnosis synthesis      │
                       └───────────────────┬───────────────────┘
                                           │
                                           ▼
                       ┌───────────────────────────────────────┐
                       │         IntegratedResponse            │
                       │   - Diagnosis summary & Confidence %  │
                       │   - Symptoms & Likely Pathogen Causes │
                       │   - Prevention & Management Actions   │
                       │   - Extension Sources & Warnings      │
                       └───────────────────────────────────────┘
```

---

## 3. Key Components & Implementation

### 3.1 Agricultural Knowledge Base (`data/knowledge_base/`)
- **Document Store**: `agricultural_documents.json` contains comprehensive, structured entries for all **38 PlantVillage canonical classes** (across 14 crop species).
- **Grounded Information**: Every entry includes specific pathogen taxonomy (e.g., *Alternaria solani*, *Venturia inaequalis*, *Phytophthora infestans*, *Xanthomonas* spp.), microclimate risk factors, cultural prevention practices, chemical/biological management protocols, and authentic extension citations (USDA-ARS, UC IPM, Cornell Extension, Purdue, Penn State, UF/IFAS).
- **Healthy Crop Care**: Specific plant care, pruning, irrigation, and nutrition guidelines for all 12 healthy crop classes.

### 3.2 Vector Index & Semantic Retrieval (`src/retrieval/`)
- **Engine**: Unified `VectorStore` engine with dual-mode support:
  - **Exact Hash Map Lookup**: Instant O(1) canonical ID retrieval.
  - **Structured Semantic 256-D Embeddings**: Orthogonal domain slots for plant species (slots 0-29), disease pathology (slots 30-79), health status (slots 70-79), symptoms (slots 80-119), treatments/chemicals (slots 120-159), and environmental conditions (slots 160-199).
  - **High-Entropy Dispersion**: Tail vocabulary tokens mapped via polynomial hashing (slots 200-255).
- **Backend Adaptability**: Built-in NumPy cosine similarity fallback, with automatic FAISS (`faiss.IndexFlatIP`) and ChromaDB persistent storage integration when installed.

### 3.3 Vision Engine (`src/vision/`)
- **Model**: `PlantDiseaseCNN` featuring 4 Convolutional blocks, Batch Normalization, ReLU, Max Pooling, Global Average Pooling, a 128-dimensional bottleneck feature extractor, and a 38-class classification head.
- **Pre-Filtering & Gating**:
  - `ImageValidator`: Verifies decodability, dimension boundaries (min 32x32), and plant foliage coverage via HSV chlorophyll thresholding.
  - Non-plant images, corrupted uploads, and low-confidence predictions are cleanly rejected before generating ungrounded advice.

### 3.4 Advisory Synthesis (`src/advisory/`)
- **Generator**: Formulates structured `IntegratedResponse` payloads combining prediction metadata, evidence chunks, authoritative citations, and safety warnings.

---

## 4. Quick Start & Execution

### 4.1 Prerequisites
Python 3.10+ with `torch`, `torchvision`, `numpy`, `pillow`, `opencv-python`, `scikit-learn`.

### 4.2 Run End-to-End Prediction
```python
from src.pipeline import PlantDiseasePipeline
import numpy as np

# Initialize pipeline
pipeline = PlantDiseasePipeline()

# Predict and generate grounded advisory
result = pipeline.predict_and_advise("path/to/leaf_image.jpg")

print(f"Status: {result.status}")
print(f"Confidence: {result.confidence * 100:.1f}%")
print(f"Message: {result.user_message}")
print(f"Sources: {result.sources}")
```

### 4.3 Query Agricultural Knowledge Base Directly
```python
from src.retrieval.rag_retriever import RAGRetriever

retriever = RAGRetriever()
results = retriever.search_similar("tomato early blight alternaria concentric rings chlorothalonil", top_k=3)
for doc, score in results:
    print(f"[{score:.4f}] {doc['canonical_id']}: {doc['plant']} - {doc['disease']}")
```

### 4.4 Rebuild Knowledge Base & Vector Index
```bash
# Rebuild JSON knowledge base documents
python scripts/build_knowledge_base.py

# Rebuild and test vector store index
python -m src.retrieval.vector_store
```

---

## 5. Testing & Verification

Run the full automated test suite (133 tests):

```bash
# Run all unit and integration test suites
python -m unittest discover -s tests -p "test_*.py"

# Run end-to-end scenario tests specifically
python -m unittest tests/test_end_to_end_scenarios.py
```

### Test Coverage Summary:
- `test_end_to_end_scenarios.py`: 16 tests (disease condition queries, edge cases, failure rejections, contract completeness).
- `test_pipeline_integration.py`: 14 tests (full pipeline lifecycle, batch processing, diagnostic info).
- `test_retrieval.py`: 32 tests (exact lookup, semantic search, grounding verification, KB stats).
- `test_advisory.py`: 20 tests (evidence chunking, prompt synthesis, low-confidence suppression, safety guardrails).
- `test_vision.py`: 4 tests (CNN forward pass, embedding normalization, classifier predictions).
- `test_preprocessing.py`: 12 tests (HSV foliage ratio, dimension validation, pipeline transforms).
- `test_taxonomy_mapping.py`: 16 tests (PlantVillage 38-class metadata consistency).
- `test_module_interfaces.py`: 12 tests (contract schemas and serialization).
- `test_embeddings.py` & `test_evaluation.py`: 7 tests (visual feature extractor, metrics calculation).

---

## 6. Performance Benchmarks (CPU Baseline)

Benchmarked on standard CPU over 100 iterations (`scripts/benchmark_performance.py`):

| Pipeline Stage | Mean Latency (ms) | Median (ms) | P95 (ms) | Min / Max (ms) |
|---|---|---|---|---|
| **1. Preprocessing & Validation** | 0.961 ms | 0.893 ms | 1.288 ms | 0.7 / 1.4 ms |
| **2. Vision CNN Inference** | 11.003 ms | 11.057 ms | 11.890 ms | 9.1 / 12.0 ms |
| **3. RAG Retrieval** | 0.002 ms | 0.002 ms | 0.002 ms | 0.0 / 0.0 ms |
| **4. Advisory Generation** | 0.009 ms | 0.008 ms | 0.015 ms | 0.0 / 0.0 ms |
| **5. Full End-to-End Pipeline** | **11.275 ms** | **11.252 ms** | **12.454 ms** | **9.4 / 12.9 ms** |

- **End-to-End Throughput**: **88.7 inferences / second (FPS)** on CPU.

---

## 7. Roadmap Status

| Week | Target | Status | Deliverables |
|---|---|---|---|
| **Week 5 (Sep 8–14)** | Agricultural Knowledge Base | ✅ **Completed & Verified** | 38-class rich KB JSON, vector index persistence (`models/vector_index`) |
| **Week 6 (Sep 15–21)** | RAG Retrieval & Advisory Flow | ✅ **Completed & Verified** | `RAGRetriever`, `AdvisoryGenerator`, condition queries, grounding verification |
| **Week 7 (Sep 22–28)** | Vision + RAG Integration | ✅ **Completed & Verified** | `PlantDiseasePipeline`, end-to-end integration, edge-case failure handling |
| **Week 8 (Sep 29–Oct 5)** | Stabilization & Optimization | 🚀 **Ready for Execution** | Benchmarking suite (`benchmark_performance.py`), 133 passing tests, CPU performance profile |

---

## 8. Directory Layout

```
plant-disease-detection/
├── data/
│   ├── knowledge_base/         # Agricultural knowledge base JSON (38 classes)
│   ├── metadata/               # Canonical class taxonomies (CSV)
│   └── processed/              # Preprocessed data caches
├── models/
│   ├── plant_disease_cnn.pth   # CNN model weights
│   ├── vector_index/           # Vector store npz, documents, canonical index
│   └── visual_embeddings_cache.npz
├── reports/
│   └── benchmark_report.json   # Latency & throughput benchmark metrics
├── scripts/
│   ├── build_knowledge_base.py # Knowledge base compiler
│   ├── benchmark_performance.py# CPU/GPU latency & throughput profiler
│   └── verify_env.py           # Environment diagnostics
├── src/
│   ├── advisory/               # Advisory synthesis & prompt formatting
│   ├── contracts.py            # Typed dataclass interface contracts
│   ├── embeddings/             # Visual feature extraction & bottleneck embeddings
│   ├── pipeline.py             # End-to-end integrated prediction pipeline
│   ├── preprocessing/          # Image validation & tensor transformations
│   ├── retrieval/              # Vector store & RAG retriever
│   └── vision/                 # PlantDiseaseCNN model & classifier
└── tests/                      # 133 automated unit and integration tests
```
