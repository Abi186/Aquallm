from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import date

from app.database import get_db


# ============================================================
# FEED ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/feed",
    tags=["Feed"]
)


# ============================================================
# FEED CREATE SCHEMA
# Matches PostgreSQL feed_records table
# ============================================================

class FeedCreate(BaseModel):
    pond_id: int
    feed_date: date
    doc: int
    feed_type: str
    feed_quantity_kg: float
    feeding_frequency: int


# ============================================================
# GET FEED RECORDS
# ============================================================

@router.get("/")
def get_feed_records(
    db: Session = Depends(get_db)
):

    try:

        query = text("""
            SELECT *
            FROM feed_records
            ORDER BY feed_id
        """)

        result = db.execute(query)

        records = [
            dict(row._mapping)
            for row in result
        ]

        return {
            "count": len(records),
            "feed_records": records
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# CREATE FEED RECORD
# ============================================================

@router.post("/")
def create_feed(
    feed: FeedCreate,
    db: Session = Depends(get_db)
):

    try:

        query = text("""
            INSERT INTO feed_records
            (
                pond_id,
                feed_date,
                doc,
                feed_type,
                feed_quantity_kg,
                feeding_frequency
            )
            VALUES
            (
                :pond_id,
                :feed_date,
                :doc,
                :feed_type,
                :feed_quantity_kg,
                :feeding_frequency
            )
            RETURNING *
        """)

        result = db.execute(
            query,
            {
                "pond_id": feed.pond_id,
                "feed_date": feed.feed_date,
                "doc": feed.doc,
                "feed_type": feed.feed_type,
                "feed_quantity_kg": feed.feed_quantity_kg,
                "feeding_frequency": feed.feeding_frequency
            }
        )

        db.commit()

        record = result.fetchone()

        return {
            "message": "Feed record created successfully",
            "feed": dict(record._mapping)
        }

    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )