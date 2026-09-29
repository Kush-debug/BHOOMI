"""
IdentityResolver (BHUMI_FORENSICS_SPEC.md §5.2 — Phase 3).

Turns a raw identifier string plus an administrative location into a durable
`Parcel`, and a raw owner name into a durable `Person` — so that two
documents describing the same khasra number converge on one row instead of
staying two unrelated claims, and two spellings of one name don't get read as
an ownership change later (Phase 5).

Honesty note on person matching: BHUMI_FORENSICS_SPEC §5.2 calls for
"script-aware normalisation + a phonetic key + edit distance". A real
phonetic algorithm (Soundex/Metaphone and their equivalents) is defined for
specific scripts and doesn't have an off-the-shelf equivalent that works
correctly across Devanagari, Tamil, Telugu and Kannada without a
language-specific transliteration model — building one is out of scope for
this MVP. What's implemented instead: exact match on a normalised name
(NFKC, casefolded, whitespace-collapsed) as the primary and only
*automatic* method, with edit-distance used only to flag near-duplicate
candidates for a human to confirm — never to merge two people
automatically. This is deliberately more conservative than the spec's
description, and is called out here rather than silently underclaimed.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.parcel import Parcel, ParcelIdentifierAlias, Person, PersonAlias

EXACT = "EXACT"
ALIAS = "ALIAS"
FUZZY = "FUZZY"

_SEPARATOR_RE = re.compile(r"[\-–—_.\s]+")
_WS_RE = re.compile(r"\s+")


def _digits_to_ascii(text: str) -> str:
    """Devanagari/Tamil/Telugu/Kannada (and other Unicode) digits -> ASCII.

    Uses unicodedata.digit() rather than a hand-built table, so it covers
    every script's decimal digits Python knows about, not just the four
    languages this project currently supports.
    """
    out = []
    for ch in text:
        if ch.isdigit():
            try:
                out.append(str(unicodedata.digit(ch)))
                continue
            except (TypeError, ValueError):
                pass
        out.append(ch)
    return "".join(out)


def normalize_identifier(raw: str) -> str:
    """Normalise a khasra/khata/survey number for comparison.

    "127-2", "127 / 2", "१२७/२" all normalise to "127/2".
    """
    if not raw:
        return ""
    text = _digits_to_ascii(unicodedata.normalize("NFKC", raw)).strip()
    # Canonicalise separators to "/", but keep a single alphabetic suffix
    # (e.g. "45A") intact rather than splitting on it.
    text = _SEPARATOR_RE.sub("/", text)
    text = re.sub(r"/+", "/", text).strip("/")
    return text.lower()


def normalize_name(raw: str) -> str:
    """NFKC-normalise, casefold, collapse whitespace. The primary (and only
    automatic) basis for person matching — see module docstring."""
    if not raw:
        return ""
    text = unicodedata.normalize("NFKC", raw).strip()
    text = _WS_RE.sub(" ", text)
    return text.casefold()


def _matching_key(normalized: str) -> str:
    """A coarser key used only to narrow edit-distance candidates — collapses
    repeated characters and drops spaces/punctuation. Not a phonetic
    algorithm; see module docstring."""
    collapsed = re.sub(r"(.)\1+", r"\1", normalized)
    return re.sub(r"[^\w]", "", collapsed)


def _levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[-1]


@dataclass
class ParcelResolution:
    parcel: Parcel
    match_method: str
    confidence: float
    created: bool


@dataclass
class PersonResolution:
    person: Person
    match_method: str
    confidence: Optional[float]
    created: bool
    review_candidates: list  # PersonAlias-adjacent near-matches that were NOT auto-merged


class IdentityResolver:
    def resolve_parcel(
        self,
        db: Session,
        *,
        state: str,
        district: str,
        tehsil: str,
        village: str,
        khasra_raw: str,
    ) -> Optional[ParcelResolution]:
        """Resolve (or create) the Parcel a khasra number + location refers to.

        Returns None if there is no usable khasra number to resolve on — a
        parcel is never created from a location alone.
        """
        khasra_norm = normalize_identifier(khasra_raw)
        if not khasra_norm:
            return None

        key_parts = [
            (state or "").strip().casefold(),
            (district or "").strip().casefold(),
            (tehsil or "").strip().casefold(),
            (village or "").strip().casefold(),
            khasra_norm,
        ]
        parcel_key = "|".join(key_parts)

        existing = db.query(Parcel).filter(Parcel.parcel_key == parcel_key).first()
        if existing:
            self._record_alias_if_new(db, existing, khasra_raw, khasra_norm, EXACT, 1.0)
            return ParcelResolution(existing, EXACT, 1.0, created=False)

        # Alias lookup: the same normalised identifier already resolved to a
        # parcel in this exact village under a different raw spelling.
        alias = (
            db.query(ParcelIdentifierAlias)
            .join(Parcel, ParcelIdentifierAlias.parcel_id == Parcel.id)
            .filter(
                ParcelIdentifierAlias.normalized == khasra_norm,
                Parcel.state.ilike(state or ""),
                Parcel.district.ilike(district or ""),
                Parcel.tehsil.ilike(tehsil or ""),
                Parcel.village.ilike(village or ""),
            )
            .first()
        )
        if alias:
            parcel = db.query(Parcel).filter(Parcel.id == alias.parcel_id).first()
            self._record_alias_if_new(db, parcel, khasra_raw, khasra_norm, ALIAS, 0.9)
            return ParcelResolution(parcel, ALIAS, 0.9, created=False)

        parcel = Parcel(
            parcel_key=parcel_key,
            state=state or "",
            district=district or "",
            tehsil=tehsil or "",
            village=village or "",
            khasra_number_norm=khasra_norm,
        )
        db.add(parcel)
        db.flush()
        self._record_alias_if_new(db, parcel, khasra_raw, khasra_norm, EXACT, 1.0)
        return ParcelResolution(parcel, EXACT, 1.0, created=True)

    def _record_alias_if_new(
        self, db: Session, parcel: Parcel, raw: str, normalized: str, method: str, confidence: float
    ) -> None:
        exists = (
            db.query(ParcelIdentifierAlias)
            .filter(ParcelIdentifierAlias.parcel_id == parcel.id, ParcelIdentifierAlias.raw_identifier == raw)
            .first()
        )
        if exists:
            return
        db.add(
            ParcelIdentifierAlias(
                parcel_id=parcel.id,
                raw_identifier=raw,
                normalized=normalized,
                match_method=method,
                confidence=confidence,
            )
        )

    def resolve_person(
        self, db: Session, raw_name: str, *, fuzzy_max_distance: int = 2
    ) -> Optional[PersonResolution]:
        """Resolve (or create) the Person an owner/father name refers to.

        Automatic merging happens only on an exact normalised-name match.
        Near-matches (small edit distance on the coarse matching key) are
        returned as `review_candidates`, never auto-merged — see module
        docstring on why a real phonetic match isn't implemented here.
        """
        if not raw_name or not raw_name.strip():
            return None

        normalized = normalize_name(raw_name)
        if not normalized:
            return None

        existing = db.query(Person).filter(Person.normalized_name == normalized).first()
        if existing:
            self._record_person_alias_if_new(db, existing, raw_name, EXACT, 1.0)
            return PersonResolution(existing, EXACT, 1.0, created=False, review_candidates=[])

        key = _matching_key(normalized)
        review_candidates = []
        if key:
            candidates = db.query(Person).filter(Person.matching_key == key).all()
            for cand in candidates:
                dist = _levenshtein(normalized, cand.normalized_name)
                if 0 < dist <= fuzzy_max_distance:
                    review_candidates.append(cand)

        person = Person(canonical_name=raw_name.strip(), normalized_name=normalized, matching_key=key)
        db.add(person)
        db.flush()
        self._record_person_alias_if_new(db, person, raw_name, EXACT, 1.0)
        return PersonResolution(
            person,
            EXACT,
            1.0,
            created=True,
            review_candidates=review_candidates,
        )

    def _record_person_alias_if_new(
        self, db: Session, person: Person, raw: str, method: str, confidence: float
    ) -> None:
        exists = (
            db.query(PersonAlias)
            .filter(PersonAlias.person_id == person.id, PersonAlias.raw_name == raw)
            .first()
        )
        if exists:
            return
        db.add(PersonAlias(person_id=person.id, raw_name=raw, match_method=method, confidence=confidence))


identity_resolver = IdentityResolver()
