# Pydantic schemas for request validation and response serialization.
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ReportUpdate(BaseModel):
    final_findings: str
    final_impression: str


class ReportRead(BaseModel):
    id: int
    created_at: datetime
    updated_at: datetime
    image_path: str
    original_filename: str
    engine_name: str
    is_mock: bool
    ai_findings: str
    ai_impression: str
    final_findings: str
    final_impression: str
    status: str
    approved_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
