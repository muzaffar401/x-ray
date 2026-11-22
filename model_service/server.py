# Standalone FastAPI model service hosting CXR-LLaVA (ECOFRI/CXR-LLAVA-v2).
import io
import os
from contextlib import asynccontextmanager
from typing import Any, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile, status
from PIL import Image
from pydantic import BaseModel

SAFETY_DISCLAIMER = (
    "AI-generated DRAFT. Must be reviewed and approved by a qualified radiologist. Not a final diagnosis."
)
MODEL_NAME = "ECOFRI/CXR-LLAVA-v2"

# Global state for loaded model and device
model_state: dict[str, Any] = {
    "model": None,
    "device": "cpu",
    "is_mock": False,
}


def load_cxr_model() -> None:
    """Load CXR-LLaVA model once at startup."""
    mock_env = os.environ.get("MOCK_MODEL", "0").strip().lower()
    if mock_env in ("1", "true", "yes"):
        model_state["is_mock"] = True
        model_state["device"] = "mock-cpu"
        model_state["model"] = "mock_instance"
        return

    import torch
    from transformers import AutoModel

    device = "cuda" if torch.cuda.is_available() else "cpu"
    # Load model using official repository identifier and trust_remote_code=True
    model = AutoModel.from_pretrained(MODEL_NAME, trust_remote_code=True)
    model = model.to(device)
    model.eval()

    model_state["model"] = model
    model_state["device"] = device
    model_state["is_mock"] = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load model on startup
    load_cxr_model()
    yield
    # Clean up on shutdown
    model_state["model"] = None


app = FastAPI(
    title="CXR-LLaVA Inference Service",
    description="GPU-hosted inference microservice for chest X-ray interpretation.",
    lifespan=lifespan,
)


def verify_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> str:
    """Verify incoming X-API-Key against MODEL_SERVICE_KEY environment variable."""
    expected_key = os.environ.get("MODEL_SERVICE_KEY")
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: MODEL_SERVICE_KEY is not set.",
        )
    if not x_api_key or x_api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
        )
    return x_api_key


class GenerateResponse(BaseModel):
    findings: str
    impression: str
    model_name: str
    disclaimer: str


@app.get("/health")
def health() -> dict[str, Any]:
    """Health check endpoint reporting model status and device."""
    return {
        "status": "ok",
        "model_loaded": model_state["model"] is not None,
        "device": model_state["device"],
        "is_mock": model_state["is_mock"],
        "disclaimer": SAFETY_DISCLAIMER,
    }


def _run_model_inference(pil_image: Image.Image) -> str:
    """Run inference using the official CXR-LLaVA prompt and method."""
    if model_state["is_mock"]:
        return (
            "No focal consolidation, pneumothorax, or large pleural effusion. "
            "Cardiomediastinal silhouette is within normal limits. Bony structures are intact."
        )

    model = model_state["model"]
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model is not loaded on this server.",
        )

    # Use the official CXR-LLaVA chat prompt format from the repository documentation
    chat = [
        {
            "role": "system",
            "content": "You are a helpful radiologist. Try to interpret chest x ray image and answer to the question that user provides.",
        },
        {
            "role": "user",
            "content": "<image>\nWrite a radiologic report on the given chest radiograph, including information about atelectasis, cardiomegaly, consolidation, pulmonary edema, pleural effusion, and pneumothorax.\n",
        },
    ]

    try:
        # Preferred: generate_cxr_repsonse with official prompt template
        if hasattr(model, "generate_cxr_repsonse"):
            return model.generate_cxr_repsonse(chat=chat, pil_image=pil_image, temperature=0, top_p=1)
        # Fallback: direct write_radiologic_report helper
        if hasattr(model, "write_radiologic_report"):
            return model.write_radiologic_report(pil_image)
        raise RuntimeError("Model does not expose expected inference methods.")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference execution failed: {str(exc)}",
        )


@app.post("/generate", response_model=GenerateResponse)
async def generate(
    file: UploadFile = File(...),
    _: str = Depends(verify_api_key),
) -> GenerateResponse:
    """Accept a PNG/JPEG chest X-ray and return generated draft report."""
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    try:
        image = Image.open(io.BytesIO(contents))
        image.load()
        # Convert grayscale/palette/RGBA to RGB
        if image.mode != "RGB":
            image = image.convert("RGB")
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or unreadable image file.")

    findings_text = _run_model_inference(image)

    # TODO: CXR-LLaVA official implementation does not generate a separate impression section.
    # The impression field is intentionally returned as an empty string to be edited by the radiologist.
    impression_text = ""

    return GenerateResponse(
        findings=findings_text,
        impression=impression_text,
        model_name=MODEL_NAME,
        disclaimer=SAFETY_DISCLAIMER,
    )
