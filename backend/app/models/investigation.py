"""
InvestigationCase (BHUMI_FORENSICS_SPEC.md §3.3, §5.9 — Phase 6).

The unit an officer actually works from: one case per parcel with at least
one active (OPEN or IN_REVIEW) `Finding`, carrying a deterministic
`priority_score`/`priority_band` so the queue orders itself instead of
requiring a human to triage every finding by hand.

The assign/comment/resolve *workflow* (Investigation Center UI, actually
acting on `assigned_to`/`comments`/`resolution`) is Phase 7 — spec's own
phase table puts "Officer workflow" one phase after "Sufficiency &
prioritisation". This model exists now because `PriorityScorer` needs
somewhere to write its output; the fields Phase 7 will operate on
(`assigned_to`, `comments`, `resolution`) are declared and already protected
from being overwritten by regeneration, but nothing in this phase sets them.

Officer-owned once touched: `status` moved off OPEN, or `assigned_to` set.
Regeneration (`investigation_service.py`) refreshes `finding_ids`/
`priority_score`/`priority_band` on every SCORE stage run for an
officer-owned case (new evidence should still update the score an officer
sees) but never touches `assigned_to`, `comments`, `resolution`, or
`sla_due_at` once they exist, and never reopens or auto-closes a case a
human has already moved off OPEN — see `is_officer_owned`.
"""
from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.types import JSON

from app.database.base import Base

STATUS_OPEN = "OPEN"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_CLOSED = "CLOSED"

_OFFICER_OWNED_STATUSES = (STATUS_IN_PROGRESS, STATUS_CLOSED)


class InvestigationCase(Base):
    __tablename__ = "investigation_cases"

    id = Column(Integer, primary_key=True, index=True)
    # One case per parcel — a parcel's active findings are triaged together,
    # not as N separate queue entries for the same underlying investigation.
    parcel_id = Column(Integer, ForeignKey("parcels.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    finding_ids = Column(JSON, default=list)
    priority_score = Column(Float, nullable=True)  # None only if every finding lacked a computable priority
    priority_band = Column(String(10), nullable=True, index=True)  # CRITICAL | HIGH | MEDIUM | LOW
    priority_breakdown_json = Column(JSON, default=dict)  # the winning finding's PriorityScorer terms

    assigned_to = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String(15), default=STATUS_OPEN, index=True)
    opened_at = Column(DateTime, default=datetime.utcnow)
    sla_due_at = Column(DateTime, nullable=True)
    comments = Column(JSON, default=list)  # Phase 7 populates; declared now so the shape is stable
    resolution = Column(Text, nullable=True)

    engine_version = Column(String(30), default="phase6-investigation-v1")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_officer_owned(self) -> bool:
        return self.status in _OFFICER_OWNED_STATUSES or self.assigned_to is not None
