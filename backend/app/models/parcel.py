"""
Parcel identity layer (BHUMI_FORENSICS_SPEC.md §3.2 — Phase 3).

`Parcel` is the durable entity documents are evidence ABOUT — the thing that
persists across years and documents, unlike a `Document` or a `Claim`. Two
documents describing the same khasra number in the same village must resolve
to the same `Parcel` row; that convergence is what later phases (timeline,
transitions, contradictions) are built on.

`Person` is the equivalent durable entity for landowners, so two spellings of
one name don't get reported as an ownership change in Phase 5.

Both entities keep an alias table recording every raw string that resolved to
them and how (`EXACT` / `ALIAS` / `FUZZY`), so a resolution is always
explainable rather than a silent merge.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.base import Base


class Parcel(Base):
    __tablename__ = "parcels"

    id = Column(Integer, primary_key=True, index=True)
    # Unique, normalised composite key: state|district|tehsil|village|khasra.
    # This — not the id — is what a second document's khasra number is looked
    # up against to decide "same parcel or a new one".
    parcel_key = Column(String(300), nullable=False, unique=True, index=True)

    state = Column(String(100), nullable=False)
    district = Column(String(100), nullable=False)
    tehsil = Column(String(100), nullable=False)
    village = Column(String(150), nullable=False)
    village_id = Column(Integer, ForeignKey("villages.id"), nullable=True)  # set when resolved to the location hierarchy

    khasra_number_norm = Column(String(100), nullable=False, index=True)
    khata_number_norm = Column(String(100), nullable=True, index=True)

    status = Column(String(20), default="ACTIVE")
    first_seen_year = Column(Integer, nullable=True)
    last_seen_year = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    aliases = relationship("ParcelIdentifierAlias", back_populates="parcel", cascade="all, delete-orphan")


class ParcelIdentifierAlias(Base):
    """Every raw identifier string that has ever resolved to this parcel."""

    __tablename__ = "parcel_identifier_aliases"

    id = Column(Integer, primary_key=True, index=True)
    parcel_id = Column(Integer, ForeignKey("parcels.id", ondelete="CASCADE"), nullable=False, index=True)
    raw_identifier = Column(String(200), nullable=False)
    normalized = Column(String(200), nullable=False, index=True)
    match_method = Column(String(20), default="EXACT")  # EXACT | ALIAS | FUZZY
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    parcel = relationship("Parcel", back_populates="aliases")


class Person(Base):
    __tablename__ = "persons"

    id = Column(Integer, primary_key=True, index=True)
    canonical_name = Column(String(200), nullable=False)
    # NFKC-normalised, casefolded, whitespace-collapsed. Exact match on this
    # is the primary resolution method (see IdentityResolver.resolve_person).
    normalized_name = Column(String(200), nullable=False, index=True)
    # NOT a true cross-script phonetic algorithm (Soundex/Metaphone don't
    # apply to Devanagari/Tamil/etc. script directly, and building one is out
    # of scope for the MVP). This is a coarser matching key — see the
    # docstring on IdentityResolver._matching_key — used only to narrow
    # candidates for an edit-distance check, never to merge on its own.
    matching_key = Column(String(200), nullable=True, index=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    aliases = relationship("PersonAlias", back_populates="person", cascade="all, delete-orphan")


class PersonAlias(Base):
    __tablename__ = "person_aliases"

    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id", ondelete="CASCADE"), nullable=False, index=True)
    raw_name = Column(String(200), nullable=False)
    script = Column(String(20), nullable=True)  # detected script/language of the raw name, when known
    match_method = Column(String(20), default="EXACT")  # EXACT | ALIAS | FUZZY
    confidence = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    person = relationship("Person", back_populates="aliases")
