from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.auth.rbac import CAN_READ_LOCATIONS, require_roles
from app.models.user import User
from app.models.location import State, District, Tehsil, Village
from app.schemas.location import StateResponse, DistrictResponse, TehsilResponse, VillageResponse

router = APIRouter(prefix="/locations", tags=["Administrative Location Master Data"])

@router.get("/states", response_model=List[StateResponse])
def get_all_states(
    type: Optional[str] = None,  # STATE or UNION_TERRITORY
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_LOCATIONS)),
):
    """
    Returns all 28 Indian States and 8 Union Territories sorted alphabetically.
    """
    query = db.query(State)
    if active_only:
        query = query.filter(State.is_active == True)
    if type:
        query = query.filter(State.type == type.upper())
    return query.order_by(State.name.asc()).all()

@router.get("/states/{state_id}/districts", response_model=List[DistrictResponse])
def get_districts_by_state(
    state_id: int,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_LOCATIONS)),
):
    """
    Returns all districts for a given State or Union Territory.
    """
    state = db.query(State).filter(State.id == state_id).first()
    if not state:
        raise HTTPException(status_code=404, detail="State/UT not found")

    query = db.query(District).filter(District.state_id == state_id)
    if active_only:
        query = query.filter(District.is_active == True)
    return query.order_by(District.name.asc()).all()

@router.get("/districts/{district_id}/tehsils", response_model=List[TehsilResponse])
def get_tehsils_by_district(
    district_id: int,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_LOCATIONS)),
):
    """
    Returns all Tehsils / Taluks / Subdivisions for a given District.
    """
    district = db.query(District).filter(District.id == district_id).first()
    if not district:
        raise HTTPException(status_code=404, detail="District not found")

    query = db.query(Tehsil).filter(Tehsil.district_id == district_id)
    if active_only:
        query = query.filter(Tehsil.is_active == True)
    return query.order_by(Tehsil.name.asc()).all()

@router.get("/tehsils/{tehsil_id}/villages", response_model=List[VillageResponse])
def get_villages_by_tehsil(
    tehsil_id: int,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_LOCATIONS)),
):
    """
    Returns all revenue villages / Mauzas for a given Tehsil / Taluk.
    """
    tehsil = db.query(Tehsil).filter(Tehsil.id == tehsil_id).first()
    if not tehsil:
        raise HTTPException(status_code=404, detail="Tehsil not found")

    query = db.query(Village).filter(Village.tehsil_id == tehsil_id)
    if active_only:
        query = query.filter(Village.is_active == True)
    return query.order_by(Village.name.asc()).all()
