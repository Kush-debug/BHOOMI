"""
Request bodies for the Phase 7 officer workflow (BHUMI_FORENSICS_SPEC.md
§5.9/§6 — investigations + evidence-linked verification).
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field


class AssignCaseRequest(BaseModel):
    assigned_to: int = Field(..., description="User id of the officer this case is assigned to")


class CommentCaseRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)


class ResolveCaseRequest(BaseModel):
    resolution: str = Field(..., min_length=1, max_length=4000, description="Why this case is being closed")


class ResolveFindingRequest(BaseModel):
    resolution_status: Literal["IN_REVIEW", "RESOLVED", "DISMISSED"]
    resolution_note: Optional[str] = Field(None, max_length=4000)


class CorrectClaimRequest(BaseModel):
    new_value: str = Field(..., min_length=1, description="The corrected value for this claim")
    notes: Optional[str] = Field(None, max_length=2000)
