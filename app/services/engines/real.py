# Real inference engine communicating with remote CXR-LLaVA GPU model service.
import json
import os
import urllib.error
import urllib.request
import uuid
from typing import Any

from fastapi import HTTPException, status

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
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"

        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "X-API-Key": self.api_key,
            "ngrok-skip-browser-warning": HEADER_NGROK_SKIP,
            "User-Agent": "XRayReportAI/1.0",
        }

        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="xray.png"\r\n'
            f"Content-Type: image/png\r\n\r\n"
        ).encode("utf-8") + image_png_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

        req = urllib.request.Request(target_url, data=body, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            # Map specific status codes from remote model service to friendly messages
            if exc.code == 503:
                msg = "The AI model is out of memory or still loading. Try again in a minute."
            elif exc.code == 504:
                msg = "The AI model took too long."
            elif exc.code == 401:
                msg = "The model service key is wrong."
            else:
                msg = "The AI model service encountered an unexpected error."
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=msg,
            ) from exc
        except (TimeoutError, urllib.error.URLError, Exception) as exc:
            # Check for socket/network timeout
            is_timeout = isinstance(exc, TimeoutError) or (
                isinstance(exc, urllib.error.URLError) and isinstance(getattr(exc, "reason", None), TimeoutError)
            )
            if is_timeout:
                msg = "The AI model took too long."
            else:
                msg = "The AI model service encountered an unexpected error."
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=msg,
            ) from exc

        return {
            "findings": data.get("findings", ""),
            "impression": data.get("impression", ""),
            "engine_name": data.get("model_name", "ECOFRI/CXR-LLAVA-v2"),
            "is_mock": False,
        }
