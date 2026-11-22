# Pydantic schemas for request validation and response serialization.
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class UserRead(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class LoginRequest(BaseModel):
    username: str
    password: str


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
    created_by: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)
