# Unseen Dataset Adaptation Checklist

> **Milestone**: Sprint 10 & T-7 to T-1 Readiness  
> **Target**: Rapid ingestion, few-shot embedding prototype indexing, and RAG knowledge expansion for unseen crops and diseases.

---

## 1. Phase A: Dataset Intake & Inspection (T-7 to T-5)

- [ ] **Data Format Verification**
  - [ ] Inspect image resolution (minimum $32 \times 32$, target $224 \times 224$).
  - [ ] Validate image decodability (PNG, JPEG, WebP) and 3-channel RGB structure.
  - [ ] Run automated foliage integrity gating (`src/preprocessing/image_validator.py` chlorophyll greenness $> 5\%$).

- [ ] **Taxonomy & Class Label Analysis**
  - [ ] Extract class label names from directory tree or metadata CSV.
  - [ ] Split labels into `(Crop/Plant, Pathogen/Disease)` pairs.
  - [ ] Generate normalized canonical identifiers (e.g., `cassava_brown_streak`, `wheat_leaf_rust`).
  - [ ] Identify novel crop types vs. known crops with new diseases.

- [ ] **Partitioning Support vs. Query Sets**
  - [ ] Extract $K$-shot support images per class (recommended $K = 5$ to $10$).
  - [ ] Reserve remaining images for validation and evaluation query sets.

---

## 2. Phase B: Few-Shot Visual Embedding & Prototype Registration (T-4 to T-3)

- [ ] **Visual Feature Extraction**
  - [ ] Run `VisualEmbeddingExtractor` (`src/embeddings/visual_embeddings.py`) across all support images.
  - [ ] Verify 128-dimensional bottleneck feature vector generation.
  - [ ] Normalize each feature embedding with L2 Euclidean unit norm.

- [ ] **Class Centroid Prototype Computation**
  - [ ] Compute mean vector centroid for each unseen class:
    $$\mathbf{c}_k = \frac{1}{K} \sum_{i=1}^K \mathbf{e}_{k, i}, \quad \mathbf{p}_k = \frac{\mathbf{c}_k}{\|\mathbf{c}_k\|_2}$$
  - [ ] Register new prototype vectors into `FewShotAdaptationEngine.prototypes` dictionary.

---

## 3. Phase C: RAG Knowledge Base Dynamic Indexing (T-3 to T-2)

- [ ] **Pathology Profile Compilation**
  - [ ] For each unseen class, compile structured agronomic metadata:
    - **Visual Symptoms**: Leaf lesions, stem streaks, pustule geometry, discoloration patterns.
    - **Causal Pathogen**: Latin taxonomy, bacterial/fungal/viral etiology, insect vectors.
    - **Microclimate Risk Factors**: Temperature thresholds, relative humidity %, leaf wetness duration.
    - **Cultural Prevention Practices**: Certified clean seed/stem stock, crop rotation, canopy spacing.
    - **Targeted Management Protocols**: Approved chemical protectants, biofungicides, resistance management.
    - **Authoritative Citations**: Extension agencies (USDA-ARS, CIMMYT, IRRI, CGIAR, ICAR, UC IPM).

- [ ] **Vector Store Index Update**
  - [ ] Inject 256-D structured semantic vector profiles into `VectorStore` (`src/retrieval/vector_store.py`).
  - [ ] Rebuild $O(1)$ hash map lookup index and cosine similarity index.

---

## 4. Phase D: End-to-End Validation & Dry Run (T-2 to T-1)

- [ ] **Classification & Inference Latency Check**
  - [ ] Run `adapter.classify(query_image)` on unseen query images.
  - [ ] Verify confidence scores and operational status (`SUPPORTED` for confidence $\ge 0.60$).
  - [ ] Verify inference latency meets real-time budget ($< 30\text{ ms}$ on CPU).

- [ ] **Advisory Synthesis Grounding Verification**
  - [ ] Verify that `predict_and_advise()` generates typed `IntegratedResponse` payloads.
  - [ ] Confirm `advisory.management` contains substantive treatment steps.
  - [ ] Ensure non-generic authoritative citations are attached.

- [ ] **Automated Test Run**
  - [ ] Execute `python -m unittest discover -s tests -p "test_*.py"` (all 138 tests passing).
  - [ ] Execute `python scripts/adapt_unseen_dataset.py`.
  - [ ] Generate final adaptation report (`reports/unseen_adaptation_results.json`).
