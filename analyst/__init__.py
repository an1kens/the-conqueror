"""Vision analyst — learns from app gameplay sessions and tunes balance."""

from analyst.recommender import analyze
from analyst.telemetry import GameplayRecorder
from analyst.tuner import apply_analysis

__all__ = ["GameplayRecorder", "analyze", "apply_analysis"]
