"""
EvidenceSufficiencyScore (BHUMI_FORENSICS_SPEC.md §3.3, §5.7 — Phase 6).

Persisted breakdown of one sufficiency computation — "score breakdown
visible and reproducible" (§9 Phase 6 gate) means more than returning a
number: it means storing which components went into it, their weights, and
whether each was actually computable, so the same score can be inspected
later without re-deriving it from scratch and without trusting a number that
arrived with no explanation.

One row per (scope_type, scope_id), upserted every time the SCORE pipeline
stage runs for that scope. Not append-only like `Claim`/`OcrRun` — a
sufficiency score is a recomputed snapshot of current belief, not a fact
that was asserted once and must be preserved forever; overwriting it on
recompute is the correct behaviour; `computed_at` is what tells you how
fresh it is.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String
from sqlalchemy.types import JSON

from app.database.base import Base

SCOPE_PARCEL = "PARCEL"
SCOPE_FINDING = "FINDING"


class EvidenceSufficiencyScore(Base):
    __tablename__ = "evidence_sufficiency_scores"

    id = Column(Integer, primary_key=True, index=True)
    scope_type = Column(String(10), nullable=False, index=True)  # PARCEL | FINDING
    scope_id = Column(Integer, nullable=False, index=True)

    formula_version = Column(String(30), nullable=False)
    # {component_name: {value: float|None, weight: float, available: bool, basis: str}}
    components_json = Column(JSON, nullable=False, default=dict)
    # None when every component was unavailable — never defaulted to a number.
    overall_score = Column(Float, nullable=True)

    computed_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
