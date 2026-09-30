"""
Adaptation Package for Plant Disease Detection & Grounded Advisory System.
Enables few-shot visual prototype learning, dynamic knowledge base augmentation,
and unseen dataset rapid adaptation.
"""

from src.adaptation.adaptation_pipeline import (
    FewShotAdaptationEngine,
    AdaptedClassProfile,
    AdaptationResult
)
from src.adaptation.baseline_freeze import BaselineFreezer

__all__ = [
    "FewShotAdaptationEngine",
    "AdaptedClassProfile",
    "AdaptationResult",
    "BaselineFreezer"
]
