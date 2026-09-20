from typing import Optional, List
from pydantic import BaseModel

class StateResponse(BaseModel):
    id: int
    name: str
    code: str
    type: str  # STATE or UNION_TERRITORY
    is_active: bool

    class Config:
        from_attributes = True

class DistrictResponse(BaseModel):
    id: int
    state_id: int
    name: str
    code: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True

class TehsilResponse(BaseModel):
    id: int
    district_id: int
    name: str
    code: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True

class VillageResponse(BaseModel):
    id: int
    tehsil_id: int
    name: str
    village_code: Optional[str] = None
    pincode: Optional[str] = None
    is_active: bool

    class Config:
        from_attributes = True
