# Abstract base class defining the inference engine interface.
from abc import ABC, abstractmethod
from typing import Any


class ReportEngine(ABC):
    @abstractmethod
    def generate(self, image_png_bytes: bytes) -> dict[str, Any]:
        """Generate a draft radiology report from preprocessed PNG bytes.

        Args:
            image_png_bytes: Normalized grayscale PNG image bytes.

        Returns:
            Dictionary with keys:
                - findings (str)
                - impression (str)
                - engine_name (str)
                - is_mock (bool)
        """
        pass
