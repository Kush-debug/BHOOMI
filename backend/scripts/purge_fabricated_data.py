#!/usr/bin/env python3
"""
Remove documents whose stored "OCR" output was fabricated by the deleted
HybridIndicOCREngine, or which were inserted directly by the old seed routine.

Background: ARCHITECTURE_AUDIT §4.1. The removed engine ignored the uploaded file
and returned hand-written land-record text with hand-written bounding boxes and
confidences. Any document processed while it was active may hold values that
never appeared in the source file. A resume was ingested this way and produced a
named landowner, a survey number and a registration deed number.

Detection is evidence-based, not id-based:
  A. the OCR run names an engine that fabricated its output
  B. the stored original file no longer exists on disk
  C. extracted fields carry one of the known placeholder bounding boxes

Usage:
    python scripts/purge_fabricated_data.py            # report only
    python scripts/purge_fabricated_data.py --confirm  # delete
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.session import SessionLocal  # noqa: E402
from app.models.document import Document  # noqa: E402
from app.models.ocr import Claim, OcrRun  # noqa: E402

FABRICATING_ENGINES = ("hybrid", "Hybrid Indic OCR", "hybrid_indic_ocr", "Hybrid Multilingual Indic OCR")
PLACEHOLDER_BOXES = [
    {"x": 60, "y": 200, "w": 250, "h": 35},
    {"x": 50, "y": 140, "w": 300, "h": 35},
    {"x": 50, "y": 85, "w": 300, "h": 25},
]


def reasons_for(db, doc: Document):
    found = []

    engines = {
        (r.engine_used or "")
        for r in db.query(OcrRun).filter(OcrRun.document_id == doc.id).all()
    }
    for engine in engines:
        if any(marker.lower() in engine.lower() for marker in FABRICATING_ENGINES):
            found.append(f"OCR recorded against the removed fabricating engine ('{engine}')")
            break

    if doc.file_path and not os.path.exists(doc.file_path):
        found.append(f"original file is absent from disk ({doc.file_path})")

    fields = db.query(Claim).filter(Claim.document_id == doc.id).all()
    for field in fields:
        box = field.bounding_box
        if isinstance(box, str):
            try:
                box = json.loads(box)
            except Exception:
                box = None
        if box in PLACEHOLDER_BOXES:
            found.append("extracted fields carry placeholder bounding boxes that did not come from OCR")
            break

    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--confirm", action="store_true", help="actually delete the documents")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        suspect = []
        for doc in db.query(Document).order_by(Document.id).all():
            why = reasons_for(db, doc)
            if why:
                suspect.append((doc, why))

        if not suspect:
            print("No fabricated or orphaned documents found. Nothing to do.")
            return 0

        print(f"{len(suspect)} document(s) flagged:\n")
        for doc, why in suspect:
            print(f"  [{doc.id}] {doc.file_name}")
            print(f"       status={doc.status}  source_class={doc.source_class}")
            preview = (doc.original_ocr_text or "").strip().replace("\n", " / ")[:110]
            if preview:
                print(f"       stored OCR: {preview}")
            for reason in why:
                print(f"       - {reason}")
            print()

        if not args.confirm:
            print("Report only. Re-run with --confirm to delete these documents and all")
            print("their derived OCR runs, evidence regions, claims, validation findings and pages.")
            return 0

        for doc, _ in suspect:
            db.delete(doc)  # cascades to pages, ocr_runs, evidence_regions, claims, validation_results
        db.commit()
        print(f"Deleted {len(suspect)} document(s) and all derived records.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
