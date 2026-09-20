"""
REMOVED IN PHASE 1 — delete this file (`git rm backend/tests/test_backend.py`).

The original suite's headline test,
`test_automatic_multilingual_ocr_and_identifier_protection`, passed *because* OCR
was fabricated. It processed seeded document 2, whose file path
(/app/data/demo_documents/TN_Coimbatore_Pollachi_Patta_842.pdf) does not exist in
the repository, so Tesseract failed, the deleted HybridIndicOCREngine fired, and
the test asserted on the invented Tamil text it returned.

Its worthwhile coverage has been rewritten:
  - 36 states / cascading hierarchy -> tests/test_seed_and_reference_data.py
  - admin CRUD, deactivation, RBAC  -> tests/test_seed_and_reference_data.py, tests/test_rbac.py
  - real OCR behaviour              -> tests/test_no_fabrication.py
  - dashboard and audit             -> tests/test_honest_metrics.py
"""
import pytest

pytestmark = pytest.mark.skip(
    reason="Superseded in Phase 1. Delete this file: git rm backend/tests/test_backend.py"
)


def test_placeholder():
    pass
