"""Adaptive tutoring, Socratic dialogue, and educational intelligence components."""

from app.tutoring.analytics_service import LearningAnalyticsService
from app.tutoring.explanation_engine import AdaptiveExplanationEngine
from app.tutoring.misconception_detector import MisconceptionDetector
from app.tutoring.quiz_engine import AdaptiveQuizEngine
from app.tutoring.recommendation_engine import PrerequisiteRecommendationEngine
from app.tutoring.socratic_engine import SocraticEngine
from app.tutoring.strategy_selector import StrategySelector

__all__ = [
    "AdaptiveExplanationEngine",
    "AdaptiveQuizEngine",
    "LearningAnalyticsService",
    "MisconceptionDetector",
    "PrerequisiteRecommendationEngine",
    "SocraticEngine",
    "StrategySelector",
]
