# Real inference engine communicating with remote CXR-LLaVA GPU model service.
import os
from typing import Any

from fastapi import HTTPException, status
import httpx

from app.services.engines.base import ReportEngine

TIMEOUT_SECONDS = 180.0
HEADER_NGROK_SKIP = "1"


class RealEngine(ReportEngine):
    """Inference engine delegating report generation to the external GPU model service."""

    def __init__(self, service_url: str | None = None, api_key: str | None = None) -> None:
        raw_url = service_url or os.getenv("MODEL_SERVICE_URL", "http://127.0.0.1:8000")
        self.service_url = raw_url.rstrip("/")
        self.api_key = api_key if api_key is not None else os.getenv("MODEL_SERVICE_KEY", "")

    def generate(self, image_png_bytes: bytes) -> dict[str, Any]:
        """Send chest X-ray PNG bytes to the remote model service and parse the report.

        Returns HTTP 502 Bad Gateway to the frontend if the remote service fails.
        Never falls back to mock data.
        """
        target_url = f"{self.service_url}/generate"
        files = {"file": ("xray.png", image_png_bytes, "image/png")}
        headers = {
            "X-API-Key": self.api_key,
            "ngrok-skip-browser-warning": HEADER_NGROK_SKIP,
            "User-Agent": "XRayReportAI/1.0",
        }

        try:
            with httpx.Client(timeout=TIMEOUT_SECONDS) as client:
                resp = client.post(target_url, files=files, headers=headers)

                # Map specific status codes from remote model service to friendly messages
                if resp.status_code == 503:
                    msg = "The AI model is out of memory or still loading. Try again in a minute."
                    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=msg)
                elif resp.status_code == 504:
                    msg = "The AI model took too long."
                    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=msg)
                elif resp.status_code == 401:
                    msg = "The model service key is wrong."
                    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=msg)
                elif resp.is_error:
                    msg = "The AI model service encountered an unexpected error."
                    raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=msg)

                data = resp.json()
        except HTTPException:
            raise
        except httpx.TimeoutException as exc:
            msg = "The AI model took too long."
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=msg) from exc
        except Exception as exc:
            msg = "The AI model service encountered an unexpected error."
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=msg) from exc

        return {
            "findings": data.get("findings", ""),
            "impression": data.get("impression", ""),
            "engine_name": data.get("model_name", "ECOFRI/CXR-LLAVA-v2"),
            "is_mock": False,
        }
