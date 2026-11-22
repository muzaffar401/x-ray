# Comprehensive tests for safe image inspection and conversion utilities.
import io
import pytest
from PIL import Image
import pydicom
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, generate_uid
from app.services.image_utils import validate_upload, to_png, safe_dicom_info


def make_fake_image(fmt: str = "PNG", size: tuple[int, int] = (200, 200), mode: str = "RGB") -> bytes:
    img = Image.new(mode, size, color=(128, 128, 128) if mode == "RGB" else 128)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def make_fake_dicom(
    rows: int = 4,
    cols: int = 4,
    photometric: str = "MONOCHROME2",
    modality: str = "DX",
    view_position: str = "PA",
    patient_name: str = "Fake^Patient",
    patient_id: str = "ANON12345",
    birth_date: str = "19700101",
    window_center: float | None = None,
    window_width: float | None = None,
    rescale_slope: float = 1.0,
    rescale_intercept: float = 0.0,
    pixel_values: list[int] | None = None,
) -> bytes:
    sop_class_uid = "1.2.840.10008.5.1.4.1.1.1"  # Computed Radiography Image Storage
    sop_instance_uid = generate_uid()

    ds = Dataset()
    ds.file_meta = FileMetaDataset()
    ds.file_meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds.file_meta.MediaStorageSOPClassUID = sop_class_uid
    ds.file_meta.MediaStorageSOPInstanceUID = sop_instance_uid

    ds.SOPClassUID = sop_class_uid
    ds.SOPInstanceUID = sop_instance_uid
    ds.Modality = modality
    ds.ViewPosition = view_position
    ds.Rows = rows
    ds.Columns = cols
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.SamplesPerPixel = 1
    ds.PhotometricInterpretation = photometric

    # Patient metadata to test privacy stripping
    ds.PatientName = patient_name
    ds.PatientID = patient_id
    ds.PatientBirthDate = birth_date

    if window_center is not None:
        ds.WindowCenter = window_center
    if window_width is not None:
        ds.WindowWidth = window_width

    ds.RescaleSlope = rescale_slope
    ds.RescaleIntercept = rescale_intercept

    if pixel_values is None:
        pixel_values = [i * 10 for i in range(rows * cols)]

    ds.PixelData = bytes([max(0, min(255, val)) for val in pixel_values])

    buf = io.BytesIO()
    pydicom.dcmwrite(buf, ds, enforce_file_format=True)
    return buf.getvalue()


class TestValidateUpload:
    def test_valid_png_and_jpeg(self):
        png_bytes = make_fake_image("PNG")
        jpg_bytes = make_fake_image("JPEG")
        validate_upload("test.png", png_bytes)
        validate_upload("test.jpg", jpg_bytes)
        validate_upload("test.jpeg", jpg_bytes)

    def test_valid_dicom(self):
        dcm_bytes = make_fake_dicom()
        validate_upload("chest.dcm", dcm_bytes)

    def test_disallowed_extension(self):
        png_bytes = make_fake_image("PNG")
        with pytest.raises(ValueError, match="Unsupported file format"):
            validate_upload("test.pdf", png_bytes)
        with pytest.raises(ValueError, match="Unsupported file format"):
            validate_upload("test.exe", png_bytes)

    def test_empty_file(self):
        with pytest.raises(ValueError, match="Uploaded file is empty"):
            validate_upload("empty.png", b"")

    def test_corrupt_or_fake_image(self):
        with pytest.raises(ValueError, match="Corrupted or invalid PNG image content"):
            validate_upload("fake.png", b"This is not a png file")
        with pytest.raises(ValueError, match="Corrupted or invalid JPEG image content"):
            validate_upload("fake.jpg", b"This is not a jpeg file")
        with pytest.raises(ValueError, match="Corrupted or invalid DICOM file content"):
            validate_upload("fake.dcm", b"This is not a dicom file")

    def test_size_limit_exceeded(self, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)
        oversized_bytes = b"x" * (1024 * 1024 + 10)
        with pytest.raises(ValueError, match="File size exceeds maximum allowed limit"):
            validate_upload("large.png", oversized_bytes)


class TestToPng:
    def test_rgb_jpeg_converted_to_grayscale_png(self):
        rgb_jpg = make_fake_image("JPEG", size=(300, 200), mode="RGB")
        png_bytes = to_png(rgb_jpg, "test.jpg")

        with Image.open(io.BytesIO(png_bytes)) as out_img:
            assert out_img.format == "PNG"
            assert out_img.mode == "L"
            assert out_img.size == (300, 200)

    def test_large_image_resized_to_max_1024(self):
        large_png = make_fake_image("PNG", size=(2048, 1024), mode="RGB")
        png_bytes = to_png(large_png, "large.png")

        with Image.open(io.BytesIO(png_bytes)) as out_img:
            assert out_img.format == "PNG"
            assert max(out_img.width, out_img.height) <= 1024
            assert out_img.size == (1024, 512)

    def test_dicom_monochrome2_to_png(self):
        dcm_bytes = make_fake_dicom(rows=8, cols=8, photometric="MONOCHROME2")
        png_bytes = to_png(dcm_bytes, "chest.dcm")

        with Image.open(io.BytesIO(png_bytes)) as out_img:
            assert out_img.format == "PNG"
            assert out_img.mode == "L"
            assert out_img.size == (8, 8)

    def test_dicom_monochrome1_inversion(self):
        # In MONOCHROME1, 0 is white and 255 is black. Inverted, 0 becomes black and 255 becomes white.
        pixels = [0, 255] * 2
        dcm_bytes = make_fake_dicom(rows=2, cols=2, photometric="MONOCHROME1", pixel_values=pixels)
        png_bytes = to_png(dcm_bytes, "mono1.dcm")

        with Image.open(io.BytesIO(png_bytes)) as out_img:
            out_pixels = list(out_img.tobytes())
            # Inversion check: index 0 (0) should be inverted toward 255
            assert out_pixels[0] == 255
            assert out_pixels[1] == 0


class TestSafeDicomInfo:
    def test_extracts_only_allowed_tags_and_strips_patient_data(self):
        dcm_bytes = make_fake_dicom(
            modality="CR",
            view_position="AP",
            rows=512,
            cols=512,
            patient_name="Confidential^Name",
            patient_id="ID-9999",
            birth_date="19850515",
        )

        info = safe_dicom_info(dcm_bytes)

        # Allowed tags must be present
        assert info["modality"] == "CR"
        assert info["view_position"] == "AP"
        assert info["rows"] == 512
        assert info["columns"] == 512

        # Sensitive patient identifiers must never be included
        assert "patient_name" not in info
        assert "PatientName" not in info
        assert "patient_id" not in info
        assert "PatientID" not in info
        assert "birth_date" not in info
        assert "PatientBirthDate" not in info

    def test_non_dicom_returns_empty_dict(self):
        info = safe_dicom_info(b"non-dicom-random-bytes")
        assert info == {}
