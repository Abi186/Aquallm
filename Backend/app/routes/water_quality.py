from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import date

from app.database import get_db


# ============================================================
# WATER QUALITY ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/water-quality",
    tags=["Water Quality"]
)


# ============================================================
# WATER QUALITY CREATE SCHEMA
# Matches PostgreSQL water_quality table
# ============================================================

class WaterQualityCreate(BaseModel):
    pond_id: int
    measurement_date: date
    doc: int
    temperature_c: float
    ph: float
    dissolved_oxygen: float
    salinity_ppt: float
    ammonia_mg_l: float


# ============================================================
# GET WATER QUALITY RECORDS
# ============================================================

@router.get("/")
def get_water_quality(
    db: Session = Depends(get_db)
):

    try:

        query = text("""
            SELECT *
            FROM water_quality
            ORDER BY water_id
        """)

        result = db.execute(query)

        records = [
            dict(row._mapping)
            for row in result
        ]

        return {
            "count": len(records),
            "water_quality": records
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# CREATE WATER QUALITY RECORD
# ============================================================

@router.post("/")
def create_water_quality(
    water: WaterQualityCreate,
    db: Session = Depends(get_db)
):

    try:

        query = text("""
            INSERT INTO water_quality
            (
                pond_id,
                measurement_date,
                doc,
                temperature_c,
                ph,
                dissolved_oxygen,
                salinity_ppt,
                ammonia_mg_l
            )
            VALUES
            (
                :pond_id,
                :measurement_date,
                :doc,
                :temperature_c,
                :ph,
                :dissolved_oxygen,
                :salinity_ppt,
                :ammonia_mg_l
            )
            RETURNING *
        """)

        result = db.execute(
            query,
            {
                "pond_id": water.pond_id,
                "measurement_date": water.measurement_date,
                "doc": water.doc,
                "temperature_c": water.temperature_c,
                "ph": water.ph,
                "dissolved_oxygen": water.dissolved_oxygen,
                "salinity_ppt": water.salinity_ppt,
                "ammonia_mg_l": water.ammonia_mg_l
            }
        )

        db.commit()

        record = result.fetchone()

        return {
            "message": "Water quality record created successfully",
            "water_quality": dict(record._mapping)
        }

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )