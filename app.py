"""Streamlit web app for leaf disease screening and grounded care guidance."""

from __future__ import annotations

import csv
import io
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import streamlit as st
import torch
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from transformers import AutoImageProcessor, AutoModelForImageClassification

from src.retrieval.rag_retriever import RAGRetriever


ROOT = Path(__file__).resolve().parent
MODEL_ID = os.getenv("PLANT_DISEASE_MODEL", "kimcomehome/plantvillage-vit-leaf-disease")
MODEL_LICENSE_URL = "https://huggingface.co/kimcomehome/plantvillage-vit-leaf-disease"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
CONFIDENCE_THRESHOLD = 0.60

st.set_page_config(
    page_title="LeafLens · Plant health check",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_resource(show_spinner="Loading the leaf model and care library…")
def load_services() -> tuple[Any, Any, RAGRetriever, dict[str, dict[str, str]]]:
    processor = AutoImageProcessor.from_pretrained(MODEL_ID)
    model = AutoModelForImageClassification.from_pretrained(MODEL_ID)
    model.eval()
    model.config.output_attentions = True
    retriever = RAGRetriever(
        kb_path=str(ROOT / "data/knowledge_base/agricultural_documents.json"),
        store_dir=str(ROOT / "models/vector_index"),
    )
    mapping: dict[str, dict[str, str]] = {}
    with (ROOT / "data/metadata/class_mapping.csv").open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            mapping[row["original_label"]] = row
    return processor, model, retriever, mapping


def predict(image: Image.Image, processor: Any, model: Any, mapping: dict[str, dict[str, str]]) -> tuple[list[dict[str, Any]], Image.Image]:
    inputs = processor(images=image, return_tensors="pt")
    with torch.inference_mode():
        output = model(**inputs, output_attentions=True)
        probabilities = torch.softmax(output.logits[0], dim=-1)
        count = min(5, probabilities.shape[0])
        scores, indices = torch.topk(probabilities, count)

    candidates: list[dict[str, Any]] = []
    for score, index in zip(scores.tolist(), indices.tolist()):
        raw_label = model.config.id2label.get(index, model.config.id2label.get(str(index), f"class_{index}"))
        row = mapping.get(raw_label, {})
        candidates.append({
            "raw_label": raw_label,
            "plant": row.get("plant", raw_label.replace("___", " — ").replace("_", " ")),
            "disease": row.get("disease", "Unknown class"),
            "canonical_id": row.get("canonical_id", ""),
            "health_status": row.get("health_status", ""),
            "confidence": float(score),
        })

    # ViT class-token attention highlights influential regions. It is not a lesion segmentation mask.
    attentions = getattr(output, "attentions", None)
    if not attentions:
        raise RuntimeError("The model did not return attention maps; try updating transformers.")
    cls_attention = attentions[-1][0].mean(dim=0)[0, 1:].detach().cpu().numpy()
    grid = int(round(np.sqrt(cls_attention.size)))
    if grid * grid != cls_attention.size:
        raise RuntimeError("The model returned an unsupported patch layout.")
    heat = cls_attention.reshape(grid, grid)
    heat = (heat - heat.min()) / max(float(heat.max() - heat.min()), 1e-8)
    heat_image = Image.fromarray(np.uint8(heat * 255)).resize(image.size, Image.Resampling.BICUBIC)
    heat_arr = np.asarray(heat_image, dtype=np.float32) / 255.0
    original = np.asarray(image.convert("RGB"), dtype=np.float32)
    red = np.zeros_like(original)
    red[..., 0] = 245
    red[..., 1] = 70 * (1 - heat_arr)
    overlay = np.clip(original * (1 - 0.42 * heat_arr[..., None]) + red * (0.42 * heat_arr[..., None]), 0, 255)
    return candidates, Image.fromarray(overlay.astype(np.uint8))


def section(title: str, values: list[str]) -> None:
    if values:
        st.markdown(f"#### {title}")
        for value in values:
            st.markdown(f"- {value}")


st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap');
:root { --ink:#173c32; --muted:#657c72; --green:#2f7556; --paper:#f4f7f1; }
.stApp { background:var(--paper); color:var(--ink); }
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; }
h1,h2,h3 { font-family:'Manrope',sans-serif; color:var(--ink); letter-spacing:-.03em; }
.hero { padding:2.5rem 0 1.4rem; max-width:850px; }
.eyebrow { color:var(--green); font-weight:700; letter-spacing:.14em; font-size:.75rem; text-transform:uppercase; }
.hero h1 { font-size:clamp(2.6rem,6vw,4.6rem); line-height:1.02; margin:.55rem 0 1rem; }
.hero p { font-size:1.12rem; color:#526d61; max-width:650px; line-height:1.7; }
.stButton button { border-radius:999px; min-height:3rem; font-weight:700; }
.stAlert { border-radius:16px; }
div[data-testid="stFileUploader"] { background:white; border:1px dashed #9eb8a7; border-radius:18px; padding:1rem; }
div[data-testid="stMetric"] { background:white; padding:1rem; border-radius:16px; border:1px solid #e0e8dd; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero"><div class="eyebrow">Plant health · Image screening</div><h1>Give your leaves<br> a closer look.</h1><p>Upload a clear close-up of one affected leaf to screen for common diseases, see which part of the image influenced the result, and review practical guidance from the project’s agricultural reference library.</p></div>', unsafe_allow_html=True)

with st.container(border=True):
    st.markdown("### Start with a leaf photo")
    st.caption("Best results come from one leaf filling most of the frame, in daylight, with the affected marks in focus. A whole tree or distant canopy photo is outside this model’s training conditions.")
    uploaded = st.file_uploader("Choose a leaf photo", type=["jpg", "jpeg", "png", "webp"], accept_multiple_files=False, label_visibility="collapsed")
    run = st.button("Check this leaf", type="primary", disabled=uploaded is None, use_container_width=True)

if uploaded is not None:
    if uploaded.size > MAX_UPLOAD_BYTES:
        st.error("This image is larger than 10 MB. Please choose a smaller image.")
        st.stop()
    try:
        image = Image.open(io.BytesIO(uploaded.getvalue())).convert("RGB")
    except (UnidentifiedImageError, OSError):
        st.error("We couldn’t read that image. Please upload a valid JPG, PNG, or WebP photo.")
        st.stop()
    if min(image.size) < 32:
        st.error("The image is too small to inspect. Please upload an image at least 32 pixels wide and tall.")
        st.stop()
    st.image(image, caption="Your uploaded image (processed in memory; not saved by this app)", use_container_width=True)

if run and uploaded is not None:
    try:
        processor, model, retriever, mapping = load_services()
        with st.spinner("Reviewing the leaf and matching reference guidance…"):
            candidates, overlay = predict(image, processor, model, mapping)
            result = candidates[0]
            advisory = retriever.retrieve_by_canonical_id(result["canonical_id"]) if result["canonical_id"] else None
        st.divider()
        st.markdown("## Screening result")
        if result["confidence"] < CONFIDENCE_THRESHOLD:
            st.warning(f"The image is too uncertain for a useful diagnosis ({result['confidence']:.0%} model score). Try a closer, sharper photo of the affected leaf. We’re withholding treatment guidance until there is a clearer match.")
        else:
            col_result, col_location = st.columns([0.9, 1.1], gap="large")
            with col_result:
                st.markdown(f"### {result['plant']} · {result['disease']}")
                st.metric("Model score", f"{result['confidence']:.0%}")
                st.caption("This score reflects the model’s ranking on its training classes; it is not a calibrated probability of disease.")
                if result["health_status"] == "healthy":
                    st.success("No supported disease pattern was identified. Keep monitoring the plant and compare new photos over time.")
                elif advisory:
                    section("What to look for", advisory.symptoms)
                    section("Likely causes", advisory.causes)
                    section("Care and management", advisory.management)
                    section("Prevention", advisory.prevention)
            with col_location:
                st.image(overlay, caption="Model attention estimate · warmer areas influenced the classification more. This does not outline lesion boundaries.", use_container_width=True)
            if advisory and advisory.sources:
                with st.expander("Reference sources"):
                    for source in advisory.sources:
                        st.markdown(f"- {source}")
            st.info("Use this as an initial screen, not a confirmed diagnosis. The classifier was trained on PlantVillage leaf images with controlled backgrounds; field photos and whole-tree images may produce misleading matches. Ask a local agricultural extension specialist before applying pesticides or removing plant material.")
            with st.expander("Other possible matches"):
                for item in candidates[1:]:
                    st.write(f"{item['plant']} · {item['disease']} — {item['confidence']:.1%}")
    except Exception as exc:
        st.error("The screening service could not start. Check the setup instructions and network access for the first model download.")
        with st.expander("Technical details"):
            st.code(str(exc))

st.markdown("---")
st.caption(f"Model: [PlantVillage ViT model card]({MODEL_LICENSE_URL}) · Guidance: project agricultural knowledge base · Photos are not retained by this app.")

