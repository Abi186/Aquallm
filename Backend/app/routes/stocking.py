from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import date

from app.database import get_db


# ============================================================
# STOCKING ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/stocking",
    tags=["Stocking"]
)


# ============================================================
# STOCKING CREATE SCHEMA
# Matches PostgreSQL stocking_records table
# ============================================================

class StockingCreate(BaseModel):
    pond_id: int
    stocking_date: date
    species: str
    seed_count: int
    avg_seed_weight_g: float
    stocking_density: float


# ============================================================
# GET ALL STOCKING RECORDS
# ============================================================

@router.get("/")
def get_stocking_records(
    db: Session = Depends(get_db)
):

    try:

        query = text("""
            SELECT *
            FROM stocking_records
            ORDER BY stocking_id
        """)

        result = db.execute(query)

        records = [
            dict(row._mapping)
            for row in result
        ]

        return {
            "count": len(records),
            "stocking_records": records
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# CREATE STOCKING RECORD
# ============================================================

@router.post("/")
def create_stocking(
    stocking: StockingCreate,
    db: Session = Depends(get_db)
):

    try:

        query = text("""
            INSERT INTO stocking_records
            (
                pond_id,
                stocking_date,
                species,
                seed_count,
                avg_seed_weight_g,
                stocking_density
            )
            VALUES
            (
                :pond_id,
                :stocking_date,
                :species,
                :seed_count,
                :avg_seed_weight_g,
                :stocking_density
            )
            RETURNING *
        """)

        result = db.execute(
            query,
            {
                "pond_id": stocking.pond_id,
                "stocking_date": stocking.stocking_date,
                "species": stocking.species,
                "seed_count": stocking.seed_count,
                "avg_seed_weight_g": stocking.avg_seed_weight_g,
                "stocking_density": stocking.stocking_density
            }
        )

        db.commit()

        record = result.fetchone()

        return {
            "message": "Stocking record created successfully",
            "stocking": dict(record._mapping)
        }

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )