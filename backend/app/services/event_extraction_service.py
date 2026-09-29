"""
Event extraction (BHUMI_FORENSICS_SPEC.md §3.2 LandEvent — Phase 5).

Reads `LandEvent`s out of a document's own claims, deterministically:

  - a `mutation_number` claim  -> a MUTATION event
  - a `registration_number` claim -> a REGISTRATION event

An event is only ever created from something a document *says* (a mutation
number printed on the page, grounded in OCR like any other claim). The
absence of a mutation number never creates anything here — that absence is
what `EventMatcher` reports as an EVIDENCE_GAP, and only after it has looked.

`event_date` is the document's year — the schema has no finer date signal
today (extraction doesn't yet pull mutation/registration dates). Flagged in
PHASE5_CHANGES.md, not hidden: a matched event's date precision is
"the year of the document that recorded it".

Idempotent: re-running over the same document updates the existing event
rather than adding a duplicate, keyed by (parcel, document, event_type).
"""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.finding import EVENT_MUTATION, EVENT_REGISTRATION, LandEvent
from app.models.ocr import Claim

ENGINE_VERSION = "phase5-events-v1"

# standardized_field -> event_type it attests to.
_ORDER_FIELD_TO_EVENT = {
    "mutation_number": EVENT_MUTATION,
    "registration_number": EVENT_REGISTRATION,
}


def _accepted_claims(db: Session, document_id: int) -> List[Claim]:
    return (
        db.query(Claim)
        .filter(Claim.document_id == document_id, Claim.lifecycle_status == "ACCEPTED")
        .all()
    )


def _to_float(value: Optional[str]) -> Optional[float]:
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


class EventExtractionService:
    def extract_events_for_document(self, db: Session, doc: Document, parcel_id: int) -> List[LandEvent]:
        """Create/refresh LandEvent rows for one document. Returns the events touched."""
        claims = _accepted_claims(db, doc.id)
        by_field = {c.standardized_field: c for c in claims}

        owner_claim = by_field.get("owner_name")
        area_claim = by_field.get("area")
        touched: List[LandEvent] = []

        for order_field, event_type in _ORDER_FIELD_TO_EVENT.items():
            order_claim = by_field.get(order_field)
            if not order_claim or not (order_claim.field_value or "").strip():
                continue

            dedupe_key = f"{parcel_id}:{doc.id}:{event_type}"
            event = db.query(LandEvent).filter(LandEvent.dedupe_key == dedupe_key).first()
            if event is None:
                event = LandEvent(dedupe_key=dedupe_key, parcel_id=parcel_id)
                db.add(event)

            evidence_ids = [order_claim.id]
            if owner_claim:
                evidence_ids.append(owner_claim.id)

            confidences = [
                c.confidence for c in (order_claim, owner_claim) if c is not None and c.confidence is not None
            ]

            event.parcel_id = parcel_id
            event.event_type = event_type
            event.event_date = doc.document_year
            event.order_number = (order_claim.field_value or "").strip()
            # The document records the state *after* the event, so its owner is
            # the "to" party. "from" is left NULL — this document doesn't name it;
            # TransitionAnalyzer supplies the before/after pair when matching.
            event.to_person_id = owner_claim.person_id if owner_claim else None
            event.from_person_id = None
            event.area_after = _to_float(area_claim.field_value) if area_claim else None
            event.area_before = None
            event.evidence_claim_ids = evidence_ids
            event.source_document_id = doc.id
            event.confidence = (sum(confidences) / len(confidences)) if confidences else None
            event.engine_version = ENGINE_VERSION
            touched.append(event)

        return touched


event_extraction_service = EventExtractionService()
