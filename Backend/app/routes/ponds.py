from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db


# ============================================================
# PONDS ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/ponds",
    tags=["Ponds"]
)


# ============================================================
# POND CREATE SCHEMA
# Matches PostgreSQL ponds table
# ============================================================

class PondCreate(BaseModel):
    farm_id: int
    pond_code: str
    area_acres: float
    culture_type: str
    status: str


# ============================================================
# GET ALL PONDS
# ============================================================

@router.get("/")
def get_ponds(
    db: Session = Depends(get_db)
):

    try:

        query = text("""
            SELECT *
            FROM ponds
            ORDER BY pond_id
        """)

        result = db.execute(query)

        ponds = [
            dict(row._mapping)
            for row in result
        ]

        return {
            "count": len(ponds),
            "ponds": ponds
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# CREATE POND
# ============================================================

@router.post("/")
def create_pond(
    pond: PondCreate,
    db: Session = Depends(get_db)
):

    try:

        query = text("""
            INSERT INTO ponds
            (
                farm_id,
                pond_code,
                area_acres,
                culture_type,
                status
            )
            VALUES
            (
                :farm_id,
                :pond_code,
                :area_acres,
                :culture_type,
                :status
            )
            RETURNING *
        """)

        result = db.execute(
            query,
            {
                "farm_id": pond.farm_id,
                "pond_code": pond.pond_code,
                "area_acres": pond.area_acres,
                "culture_type": pond.culture_type,
                "status": pond.status
            }
        )

        db.commit()

        record = result.fetchone()

        return {
            "message": "Pond created successfully",
            "pond": dict(record._mapping)
        }

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )