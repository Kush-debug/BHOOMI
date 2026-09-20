from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    user: Dict[str, Any]

class UserBase(BaseModel):
    username: str
    email: str
    full_name: str
    role: str = "viewer"
    department: Optional[str] = "Revenue Department"
    state: Optional[str] = "Uttar Pradesh"
    district: Optional[str] = "Kanpur Nagar"
    tehsil: Optional[str] = "Bilhaur"
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    tehsil: Optional[str] = None
    is_active: Optional[bool] = None

class UserStatusUpdate(BaseModel):
    is_active: bool

class UserPasswordReset(BaseModel):
    new_password: str

class UserResponse(UserBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class AdminStatsResponse(BaseModel):
    total_admins: int
    active_admins: int
    inactive_admins: int
    roles_distribution: Dict[str, int]
    recent_activity: List[Dict[str, Any]]
