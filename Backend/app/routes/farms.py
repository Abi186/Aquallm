from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import date

from app.database import get_db


# ============================================================
# FARMS ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/farms",
    tags=["Farms"]
)


# ============================================================
# FARM CREATE SCHEMA
# Matches PostgreSQL farms table
# ============================================================

class FarmCreate(BaseModel):
    farm_name: str
    location: str
    farm_area_acres: float
    created_at: date


# ============================================================
# GET ALL FARMS
# ============================================================

@router.get("/")
def get_farms(
    db: Session = Depends(get_db)
):

    try:

        query = text("""
            SELECT *
            FROM farms
            ORDER BY farm_id
        """)

        result = db.execute(query)

        farms = [
            dict(row._mapping)
            for row in result
        ]

        return {
            "count": len(farms),
            "farms": farms
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# CREATE FARM
# ============================================================

@router.post("/")
def create_farm(
    farm: FarmCreate,
    db: Session = Depends(get_db)
):

    try:

        query = text("""
            INSERT INTO farms
            (
                farm_name,
                location,
                farm_area_acres,
                created_at
            )
            VALUES
            (
                :farm_name,
                :location,
                :farm_area_acres,
                :created_at
            )
            RETURNING *
        """)

        result = db.execute(
            query,
            {
                "farm_name": farm.farm_name,
                "location": farm.location,
                "farm_area_acres": farm.farm_area_acres,
                "created_at": farm.created_at
            }
        )

        db.commit()

        record = result.fetchone()

        return {
            "message": "Farm created successfully",
            "farm": dict(record._mapping)
        }

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )