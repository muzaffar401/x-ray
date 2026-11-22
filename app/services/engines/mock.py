# Mock inference engine returning deterministic draft findings for development and testing.
from typing import Any
from app.services.engines.base import ReportEngine


class MockEngine(ReportEngine):
    engine_name: str = "mock-engine-v1"

    def generate(self, image_png_bytes: bytes) -> dict[str, Any]:
        return {
            "findings": (
                "[MOCK SAMPLE - NOT A REAL ANALYSIS] The lungs are clear without focal consolidation, "
                "pneumothorax, or pleural effusion. The cardiomediastinal silhouette and hilar contours "
                "are within normal limits. Visualized osseous structures show no acute abnormalities."
            ),
            "impression": (
                "No acute cardiopulmonary abnormality identified on this mock draft reading."
            ),
            "engine_name": self.engine_name,
            "is_mock": True,
        }
