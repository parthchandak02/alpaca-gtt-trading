"""Activity logging routes."""

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from models import Activity
from models import ActivityType as AT
from schemas import ActivityResponse
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api", tags=["activities"])


@router.get("/activities", response_model=list[ActivityResponse])
async def get_activities(
    symbol: str = None,
    activity_type: str = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Get activities with optional filtering."""
    try:
        query = db.query(Activity)

        if symbol:
            query = query.filter(Activity.symbol == symbol.upper())

        if activity_type:
            try:
                at_enum = AT[activity_type.upper()]
                query = query.filter(Activity.activity_type == at_enum)
            except KeyError:
                pass

        activities = query.order_by(Activity.created_at.desc()).limit(limit).all()
        return activities
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
