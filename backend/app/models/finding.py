"""
Investigation layer (BHUMI_FORENSICS_SPEC.md §3.3 — Phase 5).

Two persisted entities:

`LandEvent` — a real-world event (a mutation, a registration, a partition)
that a document attests to. Extracted deterministically from a document's
own claims (a `mutation_number` claim means a MUTATION happened), never
inferred from the *absence* of something. Events are what
`EventMatcher` searches when asking "what explains this transition?".

`Finding` — a structured investigation signal, not a verdict. A finding says
"a material change happened here with no supporting event on file" or "two
independent documents disagree about this field in this year". It carries
its evidence (claim ids, document ids), a time range, the rule that produced
it, and a recommended next action. It never says fraud, forgery or invalid
(spec §2 rule 8). `resolution_status` starts OPEN; an officer moves it.

Both are DERIVED in the sense that they are regenerated from the evidence
layer whenever a parcel's documents are (re)processed — but unlike Phase 4's
snapshots they are persisted, because a finding has a human-owned lifecycle
(assignment, resolution notes) that must survive recomputation. Regeneration
therefore only ever replaces findings that are still OPEN and system-owned;
anything an officer has touched is left alone (see analysis_service).
"""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.types import JSON

from app.database.base import Base

# LandEvent.event_type — the kinds of event a document can attest to.
EVENT_MUTATION = "MUTATION"
EVENT_REGISTRATION = "REGISTRATION"
EVENT_SALE = "SALE"
EVENT_INHERITANCE = "INHERITANCE"
EVENT_PARTITION = "PARTITION"
EVENT_CLASSIFICATION_CHANGE = "CLASSIFICATION_CHANGE"
EVENT_SURVEY_CORRECTION = "SURVEY_CORRECTION"

# Finding.finding_type
FINDING_CONTRADICTION = "CONTRADICTION"
FINDING_EVIDENCE_GAP = "EVIDENCE_GAP"
FINDING_RULE_VIOLATION = "RULE_VIOLATION"
FINDING_DUPLICATE = "DUPLICATE"
FINDING_SPATIAL_INCONSISTENCY = "SPATIAL_INCONSISTENCY"
FINDING_IDENTITY_AMBIGUITY = "IDENTITY_AMBIGUITY"

# Finding.resolution_status
RES_OPEN = "OPEN"
RES_IN_REVIEW = "IN_REVIEW"
RES_RESOLVED = "RESOLVED"
RES_DISMISSED = "DISMISSED"

_OFFICER_OWNED_STATUSES = (RES_IN_REVIEW, RES_RESOLVED, RES_DISMISSED)


class LandEvent(Base):
    __tablename__ = "land_events"

    id = Column(Integer, primary_key=True, index=True)
    parcel_id = Column(Integer, ForeignKey("parcels.id", ondelete="CASCADE"), nullable=False, index=True)

    event_type = Column(String(30), nullable=False, index=True)
    event_date = Column(Integer, nullable=True)  # year; the schema has no finer signal than document_year today
    order_number = Column(String(100), nullable=True)  # mutation / registration / deed number as extracted

    from_person_id = Column(Integer, ForeignKey("persons.id"), nullable=True)
    to_person_id = Column(Integer, ForeignKey("persons.id"), nullable=True)
    area_before = Column(Float, nullable=True)
    area_after = Column(Float, nullable=True)

    # The claims this event was read from — a mutation-number claim, the
    # owner-name claim on the same document, etc. Keeps the event walkable
    # back to real OCR evidence.
    evidence_claim_ids = Column(JSON, default=list)
    source_document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=True, index=True)

    confidence = Column(Float, nullable=True)  # confidence of the claim(s) the event was read from; never a literal
    engine_version = Column(String(30), default="phase5-events-v1")
    # Idempotency key for regeneration: (parcel, source document, event type).
    dedupe_key = Column(String(200), nullable=False, unique=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)


class Finding(Base):
    __tablename__ = "findings"

    id = Column(Integer, primary_key=True, index=True)
    finding_type = Column(String(30), nullable=False, index=True)
    parcel_id = Column(Integer, ForeignKey("parcels.id", ondelete="CASCADE"), nullable=False, index=True)
    severity = Column(String(10), default="MEDIUM", index=True)  # CRITICAL | HIGH | MEDIUM | LOW

    affected_predicates = Column(JSON, default=list)
    time_range_start = Column(Integer, nullable=True)
    time_range_end = Column(Integer, nullable=True)

    source_claim_ids = Column(JSON, default=list)
    source_document_ids = Column(JSON, default=list)

    rule_id = Column(String(60), nullable=False)
    rule_version = Column(String(20), default="v1")
    # A careful-language template + its params, rendered by the API. Kept
    # separate so the wording is auditable and can't drift per-call.
    explanation_template = Column(Text, nullable=False)
    explanation_params_json = Column(JSON, default=dict)

    # Phase 6's EvidenceSufficiencyScorer fills this. NULL now — never a
    # default number (spec §2 rule 3).
    evidence_sufficiency = Column(Float, nullable=True)
    recommended_action = Column(Text, nullable=True)

    resolution_status = Column(String(12), default=RES_OPEN, index=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    resolution_note = Column(Text, nullable=True)

    # Stable identity of "the same finding" across regenerations, so
    # reprocessing a document doesn't pile up duplicate rows.
    dedupe_key = Column(String(255), nullable=False, unique=True, index=True)
    engine_version = Column(String(30), default="phase5-findings-v1")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def is_officer_owned(self) -> bool:
        """True once an officer has moved it off OPEN — regeneration must not touch it."""
        return self.resolution_status in _OFFICER_OWNED_STATUSES
