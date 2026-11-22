# Image processing and safe inspection utilities for chest X-ray images.
import io
import array
from pathlib import Path
from typing import Any
from PIL import Image
import pydicom
from pydicom.dataset import Dataset
from app.config import settings

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".dcm"}


def validate_upload(filename: str, content_bytes: bytes) -> None:
    # Validate file extension
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed_str = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(f"Unsupported file format '{ext}'. Allowed formats are: {allowed_str}")

    # Validate file size
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(content_bytes) > max_bytes:
        raise ValueError(f"File size exceeds maximum allowed limit of {settings.MAX_UPLOAD_MB}MB.")

    if len(content_bytes) == 0:
        raise ValueError("Uploaded file is empty.")

    # Validate real file content
    if ext == ".dcm":
        try:
            pydicom.dcmread(io.BytesIO(content_bytes), stop_before_pixels=True)
        except Exception as exc:
            raise ValueError("Corrupted or invalid DICOM file content.") from exc
    elif ext in {".jpg", ".jpeg"}:
        try:
            with Image.open(io.BytesIO(content_bytes)) as img:
                img.verify()
                if img.format not in ("JPEG", "MPO"):
                    raise ValueError(f"File extension is JPEG, but content format is {img.format}.")
        except Exception as exc:
            raise ValueError("Corrupted or invalid JPEG image content.") from exc
    elif ext == ".png":
        try:
            with Image.open(io.BytesIO(content_bytes)) as img:
                img.verify()
                if img.format != "PNG":
                    raise ValueError(f"File extension is PNG, but content format is {img.format}.")
        except Exception as exc:
            raise ValueError("Corrupted or invalid PNG image content.") from exc


def _dicom_to_pil(ds: Dataset) -> Image.Image:
    # Try numpy-accelerated conversion if numpy is available
    try:
        import numpy as np

        arr = ds.pixel_array.astype(float)

        # Apply rescale slope and intercept if present
        slope = float(getattr(ds, "RescaleSlope", 1))
        intercept = float(getattr(ds, "RescaleIntercept", 0))
        arr = arr * slope + intercept

        # Apply windowing if defined
        wc = getattr(ds, "WindowCenter", None)
        ww = getattr(ds, "WindowWidth", None)
        if wc is not None and ww is not None:
            if isinstance(wc, (list, tuple, pydicom.multival.MultiValue)):
                wc = float(wc[0])
            else:
                wc = float(wc)
            if isinstance(ww, (list, tuple, pydicom.multival.MultiValue)):
                ww = float(ww[0])
            else:
                ww = float(ww)
            min_val = wc - (ww / 2.0)
            max_val = wc + (ww / 2.0)
            arr = np.clip(arr, min_val, max_val)
            if max_val > min_val:
                arr = ((arr - min_val) / (max_val - min_val)) * 255.0
            else:
                arr = np.zeros_like(arr)
        else:
            min_val = float(arr.min())
            max_val = float(arr.max())
            if max_val > min_val:
                arr = ((arr - min_val) / (max_val - min_val)) * 255.0
            else:
                arr = np.zeros_like(arr)

        # Invert MONOCHROME1 so bones appear white
        if getattr(ds, "PhotometricInterpretation", "").strip() == "MONOCHROME1":
            arr = 255.0 - arr

        uint8_arr = np.clip(arr, 0, 255).astype(np.uint8)
        return Image.fromarray(uint8_arr, mode="L")
    except (ImportError, Exception):
        # Pure Python fallback using built-in array module
        return _dicom_to_pil_fallback(ds)


def _dicom_to_pil_fallback(ds: Dataset) -> Image.Image:
    rows = int(getattr(ds, "Rows", 0))
    cols = int(getattr(ds, "Columns", 0))
    bits_alloc = int(getattr(ds, "BitsAllocated", 8))
    pixel_data = ds.PixelData

    if bits_alloc == 8:
        pixels = [float(b) for b in pixel_data]
    else:
        typecode = "h" if getattr(ds, "PixelRepresentation", 0) == 1 else "H"
        arr_vals = array.array(typecode)
        arr_vals.frombytes(pixel_data)
        pixels = [float(v) for v in arr_vals]

    # Apply rescale slope and intercept
    slope = float(getattr(ds, "RescaleSlope", 1))
    intercept = float(getattr(ds, "RescaleIntercept", 0))
    if slope != 1 or intercept != 0:
        pixels = [p * slope + intercept for p in pixels]

    # Apply windowing or min-max normalization
    wc = getattr(ds, "WindowCenter", None)
    ww = getattr(ds, "WindowWidth", None)
    if wc is not None and ww is not None:
        if isinstance(wc, (list, tuple, pydicom.multival.MultiValue)):
            wc = float(wc[0])
        else:
            wc = float(wc)
        if isinstance(ww, (list, tuple, pydicom.multival.MultiValue)):
            ww = float(ww[0])
        else:
            ww = float(ww)
        min_val = wc - (ww / 2.0)
        max_val = wc + (ww / 2.0)
        span = max_val - min_val
        if span > 0:
            pixels = [max(0.0, min(255.0, ((p - min_val) / span) * 255.0)) for p in pixels]
        else:
            pixels = [0.0] * len(pixels)
    else:
        min_val = min(pixels) if pixels else 0.0
        max_val = max(pixels) if pixels else 0.0
        span = max_val - min_val
        if span > 0:
            pixels = [((p - min_val) / span) * 255.0 for p in pixels]
        else:
            pixels = [0.0] * len(pixels)

    # Invert MONOCHROME1 so bones appear white
    if getattr(ds, "PhotometricInterpretation", "").strip() == "MONOCHROME1":
        pixels = [255.0 - p for p in pixels]

    byte_vals = bytes([int(max(0, min(255, round(p)))) for p in pixels])
    return Image.frombytes("L", (cols, rows), byte_vals)


def to_png(content_bytes: bytes, filename: str) -> bytes:
    ext = Path(filename).suffix.lower()

    if ext == ".dcm":
        ds = pydicom.dcmread(io.BytesIO(content_bytes))
        img = _dicom_to_pil(ds)
    else:
        img = Image.open(io.BytesIO(content_bytes))
        if img.mode != "L":
            img = img.convert("L")

    # Resize so the longest side is at most 1024 pixels
    if max(img.width, img.height) > 1024:
        img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)

    out_buf = io.BytesIO()
    img.save(out_buf, format="PNG")
    return out_buf.getvalue()


def safe_dicom_info(content_bytes: bytes) -> dict[str, Any]:
    try:
        ds = pydicom.dcmread(io.BytesIO(content_bytes), stop_before_pixels=True)
    except Exception:
        return {}

    # Extract strictly safe metadata tags
    info: dict[str, Any] = {}
    if "Modality" in ds and ds.Modality:
        info["modality"] = str(ds.Modality).strip()
    if "ViewPosition" in ds and ds.ViewPosition:
        info["view_position"] = str(ds.ViewPosition).strip()
    if "Rows" in ds and ds.Rows:
        info["rows"] = int(ds.Rows)
    if "Columns" in ds and ds.Columns:
        info["columns"] = int(ds.Columns)

    return info
