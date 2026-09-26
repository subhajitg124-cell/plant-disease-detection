import os
import sys
from typing import Optional, List, Dict, Any, Union

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.contracts import (
    VisionPrediction, RAGQueryInput, AdvisoryResult,
    IntegratedResponse, PredictionStatus
)
from src.retrieval.rag_retriever import RAGRetriever


class AdvisoryGenerator:
    def __init__(self, retriever: Optional[RAGRetriever] = None):
        self.retriever = retriever if retriever is not None else RAGRetriever()

    def generate_advisory(self, prediction: VisionPrediction) -> IntegratedResponse:
        status = prediction.status

        if status == PredictionStatus.NOT_A_PLANT.value:
            return IntegratedResponse(
                prediction=prediction,
                advisory=None,
                user_message=(
                    "Input image failed plant foliage validation. "
                    "Please upload a clear, well-lit photograph of a plant leaf."
                ),
                confidence=prediction.confidence,
                status=status,
                evidence=[],
                sources=[],
                warnings=["Validation failure: Non-plant or corrupted image detected."]
            )

        if status == PredictionStatus.UNCERTAIN.value:
            return IntegratedResponse(
                prediction=prediction,
                advisory=None,
                user_message=(
                    f"Prediction confidence is too low ({prediction.confidence * 100:.1f}%) "
                    "to generate a reliable advisory. "
                    "Please provide a clearer, close-up image of the affected leaf."
                ),
                confidence=prediction.confidence,
                status=status,
                evidence=[],
                sources=[],
                warnings=[
                    "Low-confidence prediction suppressed for safety.",
                    f"Confidence {prediction.confidence:.3f} is below the operational threshold."
                ]
            )

        if status == PredictionStatus.UNKNOWN.value:
            return IntegratedResponse(
                prediction=prediction,
                advisory=None,
                user_message=(
                    f"The detected pathology on {prediction.plant} does not match "
                    "any supported disease in the current knowledge base taxonomy. "
                    "Please consult a local agricultural extension specialist."
                ),
                confidence=prediction.confidence,
                status=status,
                evidence=[],
                sources=[],
                warnings=["Out-of-distribution plant disease detected — advisory unavailable."]
            )

        return self._generate_grounded_advisory(prediction)

    def _generate_grounded_advisory(
        self, prediction: VisionPrediction
    ) -> IntegratedResponse:
        warnings: List[str] = []

        rag_query = RAGQueryInput(
            plant=prediction.plant,
            disease=prediction.disease,
            canonical_id=prediction.canonical_id
        )

        advisory = self.retriever.retrieve(rag_query)

        is_grounded = self.retriever.is_grounded(advisory)
        if not is_grounded:
            warnings.append(
                "Advisory grounding quality is low — retrieved content may be generic. "
                "Verify with a certified agronomist before taking action."
            )

        evidence_chunks = self.retriever.get_evidence_chunks(advisory, max_chunks=8)
        user_message = self._synthesise_message(prediction, advisory, is_grounded)

        return IntegratedResponse(
            prediction=prediction,
            advisory=advisory,
            user_message=user_message,
            confidence=prediction.confidence,
            status=prediction.status,
            evidence=evidence_chunks,
            sources=advisory.sources,
            warnings=warnings
        )

    def _synthesise_message(
        self,
        prediction: VisionPrediction,
        advisory: AdvisoryResult,
        is_grounded: bool
    ) -> str:
        lines: List[str] = []

        conf_pct = prediction.confidence * 100
        lines.append(
            f"Diagnosis: {prediction.plant} — {prediction.disease} "
            f"({conf_pct:.1f}% confidence)."
        )

        if advisory.symptoms:
            top_symptoms = advisory.symptoms[:3]
            lines.append(
                "Observed symptoms: " + "; ".join(top_symptoms) + "."
            )

        if advisory.causes:
            lines.append(
                "Likely cause: " + advisory.causes[0] + "."
            )

        if advisory.risk_factors:
            lines.append(
                "Key risk factor: " + advisory.risk_factors[0] + "."
            )

        if advisory.prevention:
            top_prevention = advisory.prevention[:2]
            lines.append(
                "Recommended prevention: " + "; ".join(top_prevention) + "."
            )

        if advisory.management:
            top_management = advisory.management[:2]
            lines.append(
                "Treatment actions: " + "; ".join(top_management) + "."
            )

        if not is_grounded:
            lines.append(
                "Note: Advisory is based on general guidelines. "
                "Consult an agronomist for site-specific recommendations."
            )

        return " | ".join(lines)

    def generate_batch(
        self, predictions: List[VisionPrediction]
    ) -> List[IntegratedResponse]:
        return [self.generate_advisory(pred) for pred in predictions]

    def format_advisory_report(self, response: IntegratedResponse) -> str:
        pred = response.prediction
        lines = [
            "=" * 60,
            "PLANT DISEASE ADVISORY REPORT",
            "=" * 60,
            f"Plant:    {pred.plant}",
            f"Disease:  {pred.disease}",
            f"Confidence: {pred.confidence * 100:.1f}%",
            f"Status:   {response.status}",
            "",
            "ADVISORY:",
            response.user_message,
        ]

        if response.advisory:
            adv = response.advisory
            if adv.symptoms:
                lines += ["", "SYMPTOMS:"]
                lines += [f"  • {s}" for s in adv.symptoms]
            if adv.causes:
                lines += ["", "CAUSES:"]
                lines += [f"  • {c}" for c in adv.causes]
            if adv.risk_factors:
                lines += ["", "RISK FACTORS:"]
                lines += [f"  • {r}" for r in adv.risk_factors]
            if adv.prevention:
                lines += ["", "PREVENTION:"]
                lines += [f"  • {p}" for p in adv.prevention]
            if adv.management:
                lines += ["", "MANAGEMENT:"]
                lines += [f"  • {m}" for m in adv.management]
            if adv.sources:
                lines += ["", "SOURCES:"]
                lines += [f"  [{i+1}] {s}" for i, s in enumerate(adv.sources)]

        if response.warnings:
            lines += ["", "WARNINGS:"]
            lines += [f"  ⚠ {w}" for w in response.warnings]

        lines.append("=" * 60)
        return "\n".join(lines)


if __name__ == "__main__":
    generator = AdvisoryGenerator()

    pred_supported = VisionPrediction(
        plant="Apple",
        disease="Apple scab",
        canonical_id="apple_apple_scab",
        confidence=0.92,
        status="supported",
        raw_label="Apple___Apple_scab",
        model_version="vision_v1"
    )
    res = generator.generate_advisory(pred_supported)
    print(generator.format_advisory_report(res))
    print(f"\nGrounding verified: {bool(res.evidence)}")
    print(f"Sources: {res.sources}")

    print("\n" + "=" * 60)
    pred_uncertain = VisionPrediction(
        plant="Tomato",
        disease="Early blight",
        canonical_id="tomato_early_blight",
        confidence=0.38,
        status="uncertain"
    )
    res2 = generator.generate_advisory(pred_uncertain)
    print(f"Uncertain → Advisory: {res2.advisory}")
    print(f"Warning: {res2.warnings}")

    print("\n[Query-based Retrieval]")
    similar = generator.retriever.search_similar(
        "tomato late blight phytophthora infestans cool wet weather management", top_k=3
    )
    for doc, score in similar:
        print(f"  [{score:.4f}] {doc['canonical_id']} — {doc['plant']}/{doc['disease']}")
