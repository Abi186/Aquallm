from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import date

from app.database import get_db


# ============================================================
# GROWTH ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/growth",
    tags=["Growth"]
)


# ============================================================
# GROWTH CREATE SCHEMA
# Matches PostgreSQL growth_sampling table
# ============================================================

class GrowthCreate(BaseModel):
    pond_id: int
    sampling_date: date
    doc: int
    avg_weight_g: float
    biomass_kg: float
    adg_g: float
    estimated_survival_pct: float


# ============================================================
# GET ALL GROWTH RECORDS
# ============================================================

@router.get("/")
def get_growth_records(
    db: Session = Depends(get_db)
):

    try:

        query = text("""
            SELECT *
            FROM growth_sampling
            ORDER BY sampling_id
        """)

        result = db.execute(query)

        records = [
            dict(row._mapping)
            for row in result
        ]

        return {
            "count": len(records),
            "growth_records": records
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# CREATE GROWTH RECORD
# ============================================================

@router.post("/")
def create_growth(
    growth: GrowthCreate,
    db: Session = Depends(get_db)
):

    try:

        query = text("""
            INSERT INTO growth_sampling
            (
                pond_id,
                sampling_date,
                doc,
                avg_weight_g,
                biomass_kg,
                adg_g,
                estimated_survival_pct
            )
            VALUES
            (
                :pond_id,
                :sampling_date,
                :doc,
                :avg_weight_g,
                :biomass_kg,
                :adg_g,
                :estimated_survival_pct
            )
            RETURNING *
        """)

        result = db.execute(
            query,
            {
                "pond_id": growth.pond_id,
                "sampling_date": growth.sampling_date,
                "doc": growth.doc,
                "avg_weight_g": growth.avg_weight_g,
                "biomass_kg": growth.biomass_kg,
                "adg_g": growth.adg_g,
                "estimated_survival_pct": growth.estimated_survival_pct
            }
        )

        db.commit()

        record = result.fetchone()

        return {
            "message": "Growth record created successfully",
            "growth": dict(record._mapping)
        }

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )