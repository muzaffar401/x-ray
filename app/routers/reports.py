# Radiology report generation, review, and approval route handlers with auth protection.
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Report, User
from app.schemas import ReportRead, ReportUpdate
from app.security import get_current_user
from app.services.audit import log_action
from app.services.engines import get_engine
from app.services.image_utils import to_png, validate_upload
from app.services.pdf_export import generate_report_pdf

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("", response_model=ReportRead, status_code=status.HTTP_201_CREATED)
async def create_report(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    original_filename = file.filename or "uploaded_image.png"

    try:
        content_bytes = await file.read()
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {exc}",
        ) from exc

    # 1. Validate real image content and size
    try:
        validate_upload(original_filename, content_bytes)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # 2. Convert to normalized PNG
    try:
        png_bytes = to_png(content_bytes, original_filename)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Failed to process image into standard PNG format: {exc}",
        ) from exc

    # 3. Save PNG in UPLOAD_DIR using a random UUID filename (never user filename)
    random_filename = f"{uuid.uuid4().hex}.png"
    target_path = Path(settings.UPLOAD_DIR) / random_filename
    target_path.write_bytes(png_bytes)

    # 4. Generate draft report via selected engine
    engine = get_engine()
    engine_output = engine.generate(png_bytes)

    ai_findings = engine_output["findings"]
    ai_impression = engine_output["impression"]

    # 5. Save database row with initial copies in final_* fields and user attribution
    report = Report(
        image_path=str(target_path.resolve()),
        original_filename=original_filename,
        engine_name=engine_output.get("engine_name", "unknown"),
        is_mock=bool(engine_output.get("is_mock", True)),
        ai_findings=ai_findings,
        ai_impression=ai_impression,
        final_findings=ai_findings,
        final_impression=ai_impression,
        status="draft",
        approved_at=None,
        created_by=current_user.id,
    )

    db.add(report)
    db.commit()
    db.refresh(report)

    log_action(db, action="created", user_id=current_user.id, report_id=report.id, details="Report created")

    return report


@router.get("", response_model=List[ReportRead])
def list_reports(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Report]:
    return db.query(Report).order_by(Report.created_at.desc()).all()


@router.get("/{report_id}", response_model=ReportRead)
def get_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with id {report_id} not found.",
        )
    log_action(db, action="viewed", user_id=current_user.id, report_id=report.id, details="Report viewed")
    return report


@router.get("/{report_id}/image")
def get_report_image(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with id {report_id} not found.",
        )

    file_path = Path(report.image_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report image file not found on server disk.",
        )

    return FileResponse(file_path, media_type="image/png")


@router.put("/{report_id}", response_model=ReportRead)
def update_report(
    report_id: int,
    update_data: ReportUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with id {report_id} not found.",
        )

    # Only creator doctor or admin can edit
    if current_user.role != "admin" and report.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to edit this report.",
        )

    # Edits are strictly forbidden if already approved
    if report.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Report has already been approved and cannot be modified.",
        )

    report.final_findings = update_data.final_findings
    report.final_impression = update_data.final_impression
    report.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(report)
    log_action(db, action="edited", user_id=current_user.id, report_id=report.id, details="Report edited")
    return report


@router.post("/{report_id}/approve", response_model=ReportRead)
def approve_report(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with id {report_id} not found.",
        )

    # Only creator doctor or admin can approve
    if current_user.role != "admin" and report.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to approve this report.",
        )

    report.status = "approved"
    report.approved_at = datetime.now(timezone.utc)
    report.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(report)
    log_action(db, action="approved", user_id=current_user.id, report_id=report.id, details="Report approved")
    return report


@router.get("/{report_id}/pdf")
def export_report_pdf(
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report with id {report_id} not found.",
        )

    # PDF export is strictly forbidden for unapproved draft reports
    if report.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="PDF export is available only for approved reports. Please review and approve the report first.",
        )

    # Resolve reporting physician's display name
    creator = db.query(User).filter(User.id == report.created_by).first() if report.created_by else None
    approver_name = creator.username if creator else current_user.username

    pdf_bytes = generate_report_pdf(report, approver_username=approver_name)

    log_action(db, action="pdf_exported", user_id=current_user.id, report_id=report.id, details="Report PDF exported")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=report_{report.id}.pdf"},
    )
