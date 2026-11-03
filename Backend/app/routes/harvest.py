from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import date

from app.database import get_db


# ============================================================
# HARVEST ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/harvest",
    tags=["Harvest"]
)


# ============================================================
# HARVEST CREATE SCHEMA
# Matches PostgreSQL harvest_records table
# ============================================================

class HarvestCreate(BaseModel):
    pond_id: int
    harvest_date: date
    harvest_quantity_kg: float
    avg_weight_g: float
    survival_pct: float
    total_feed_kg: float
    fcr: float


# ============================================================
# GET HARVEST RECORDS
# ============================================================

@router.get("/")
def get_harvest_records(
    db: Session = Depends(get_db)
):

    try:

        query = text("""
            SELECT *
            FROM harvest_records
            ORDER BY harvest_id
        """)

        result = db.execute(query)

        records = [
            dict(row._mapping)
            for row in result
        ]

        return {
            "count": len(records),
            "harvest_records": records
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# CREATE HARVEST RECORD
# ============================================================

@router.post("/create")
def create_harvest(
    harvest: HarvestCreate,
    db: Session = Depends(get_db)
):

    try:

        query = text("""
            INSERT INTO harvest_records
            (
                pond_id,
                harvest_date,
                harvest_quantity_kg,
                avg_weight_g,
                survival_pct,
                total_feed_kg,
                fcr
            )
            VALUES
            (
                :pond_id,
                :harvest_date,
                :harvest_quantity_kg,
                :avg_weight_g,
                :survival_pct,
                :total_feed_kg,
                :fcr
            )
            RETURNING *
        """)

        result = db.execute(
            query,
            {
                "pond_id": harvest.pond_id,
                "harvest_date": harvest.harvest_date,
                "harvest_quantity_kg": harvest.harvest_quantity_kg,
                "avg_weight_g": harvest.avg_weight_g,
                "survival_pct": harvest.survival_pct,
                "total_feed_kg": harvest.total_feed_kg,
                "fcr": harvest.fcr
            }
        )

        db.commit()

        record = result.fetchone()

        return {
            "message": "Harvest record created successfully",
            "harvest": dict(record._mapping)
        }

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )