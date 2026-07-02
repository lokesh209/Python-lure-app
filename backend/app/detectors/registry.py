from ..core.config import settings
from .base import Detector
from .hipergator import HiPerGatorDetector
from .local import LocalDetector
from .mock import MockDetector


def get_detector() -> Detector:
    name = (settings.detector or "mock").lower()
    if name == "hipergator":
        return HiPerGatorDetector()
    if name == "local":
        return LocalDetector()
    return MockDetector()
