"""Authentication routes."""

from config import settings
from fastapi import APIRouter, Form, HTTPException

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(password: str = Form(...)):
    """Login endpoint - verify password."""
    if not settings.ui_password:
        # If no password is set, allow any password (development mode)
        return {"success": True, "message": "Login successful"}

    if password == settings.ui_password:
        return {"success": True, "message": "Login successful"}
    raise HTTPException(status_code=401, detail="Invalid password")
