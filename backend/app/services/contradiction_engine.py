"""
ContradictionEngine (BHUMI_FORENSICS_SPEC.md §5.6 — Phase 5).

"Which changes are actually contradictory?"

A contradiction is: the same parcel, the same predicate, the same year, with
incompatible values asserted by *independent* documents. Two spellings of
one owner name (a Phase 3 identity job, not a contradiction) don't count;
two different documents both dated 2008 that name different owners for the
same khasra number do.

Deterministic. Both conflicting claims are preserved and returned — nothing
is discarded to make the disagreement go away (spec §2 rule 4). The output
is a signal for an officer to reconcile, not an accusation against either
document.
"""
from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.models.ocr import Claim

ENGINE_VERSION = "phase5-contradictions-v1"

# Predicates worth contradiction-checking. owner/area/classification/khata
# are parcel state; father_name etc. aren't.
_CHECKED_PREDICATES = ("owner_name", "area", "land_classification", "khata_number")


def _norm(value: str | None) -> str:
    return (value or "").strip().casefold()


class ContradictionEngine:
    def detect(self, db: Session, parcel_id: int) -> List[Dict[str, Any]]:
        claims = (
            db.query(Claim)
            .filter(
                Claim.parcel_id == parcel_id,
                Claim.lifecycle_status == "ACCEPTED",
                Claim.standardized_field.in_(_CHECKED_PREDICATES),
            )
            .join(Claim.document)
            .all()
        )

        # group by (year, predicate)
        groups: Dict[tuple, List[Claim]] = {}
        for c in claims:
            year = c.document.document_year
            groups.setdefault((year, c.standardized_field), []).append(c)

        contradictions: List[Dict[str, Any]] = []
        for (year, predicate), group in sorted(groups.items()):
            distinct_values = {_norm(c.field_value) for c in group if _norm(c.field_value)}
            distinct_docs = {c.document_id for c in group}
            # Must be a genuine disagreement AND come from more than one
            # document — a single document contradicting itself is an
            # extraction bug, not a records conflict.
            if len(distinct_values) < 2 or len(distinct_docs) < 2:
                continue

            contradictions.append(
                {
                    "predicate": predicate,
                    "year": year,
                    "values": sorted({(c.field_value or "").strip() for c in group if (c.field_value or "").strip()}),
                    "source_claim_ids": sorted(c.id for c in group),
                    "source_document_ids": sorted(distinct_docs),
                    "evidence_region_ids": sorted(
                        c.evidence_region_id for c in group if c.evidence_region_id is not None
                    ),
                    "engine_version": ENGINE_VERSION,
                }
            )

        return contradictions


contradiction_engine = ContradictionEngine()
