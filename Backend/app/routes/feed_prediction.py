from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.ml.feed_model import predict_feed


router = APIRouter(
    prefix="/api/feed-prediction",
    tags=["Feed Prediction"],
)


class FeedPredictionRequest(BaseModel):
    doc: int = Field(ge=0)
    avg_weight_g: float = Field(gt=0)
    biomass_kg: float = Field(gt=0)
    temperature_c: float
    dissolved_oxygen: float = Field(ge=0)
    previous_feed_kg: float = Field(ge=0)


def run_prediction(inputs: dict) -> float:
    try:
        predicted = float(predict_feed(inputs))

        if predicted != predicted:  # NaN check
            raise ValueError("The model returned an invalid number.")

        return round(max(0.0, predicted), 2)

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Feed model prediction failed: {exc}",
        ) from exc


def normalize_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def db_error(db: Session, exc: SQLAlchemyError, where: str):
    db.rollback()
    raise HTTPException(
        status_code=500,
        detail=f"Database error in {where}: {exc.__class__.__name__}",
    ) from exc


def get_pond_in_farm(db: Session, farm_id: int, pond_number: int) -> dict:
    """Finds the real DB pond_id from (farm_id, pond_number 1..N)."""
    try:
        row = db.execute(
            text("""
                SELECT t.pond_id, t.pond_code, t.pond_number,
                       t.farm_id, t.farm_name
                FROM (
                    SELECT p.pond_id,
                           p.pond_code,
                           p.farm_id,
                           f.farm_name,
                           ROW_NUMBER() OVER (
                               PARTITION BY p.farm_id ORDER BY p.pond_id
                           ) AS pond_number
                    FROM ponds p
                    JOIN farms f ON f.farm_id = p.farm_id
                ) t
                WHERE t.farm_id = :farm_id AND t.pond_number = :pond_number
            """),
            {"farm_id": farm_id, "pond_number": pond_number},
        ).mappings().first()
    except SQLAlchemyError as exc:
        db_error(db, exc, "get_pond_in_farm")

    if not row:
        raise HTTPException(
            status_code=404,
            detail=f"Farm {farm_id} has no pond number {pond_number}.",
        )
    return dict(row)


def load_latest_inputs(db: Session, pond_id: int):
    """Latest feed, growth and water-quality records for a pond."""
    feed = db.execute(
        text("""
            SELECT feed_date, doc, feed_quantity_kg
            FROM feed_records
            WHERE pond_id = :pond_id
            ORDER BY feed_date DESC
            LIMIT 1
        """),
        {"pond_id": pond_id},
    ).mappings().first()

    growth = db.execute(
        text("""
            SELECT sampling_date, avg_weight_g, biomass_kg
            FROM growth_sampling
            WHERE pond_id = :pond_id
            ORDER BY sampling_date DESC
            LIMIT 1
        """),
        {"pond_id": pond_id},
    ).mappings().first()

    water = db.execute(
        text("""
            SELECT measurement_date, temperature_c, dissolved_oxygen
            FROM water_quality
            WHERE pond_id = :pond_id
            ORDER BY measurement_date DESC
            LIMIT 1
        """),
        {"pond_id": pond_id},
    ).mappings().first()

    if not feed or not growth or not water:
        raise HTTPException(
            status_code=404,
            detail=(
                "This pond needs feed, growth and water-quality records "
                "before a forecast can be generated."
            ),
        )

    inputs = {
        "doc": feed["doc"],
        "avg_weight_g": growth["avg_weight_g"],
        "biomass_kg": growth["biomass_kg"],
        "temperature_c": water["temperature_c"],
        "dissolved_oxygen": water["dissolved_oxygen"],
        "previous_feed_kg": feed["feed_quantity_kg"],
    }

    missing = [key for key, value in inputs.items() if value is None]

    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Some required prediction inputs are missing.",
                "missing_inputs": missing,
            },
        )

    source_dates = {
        "feed": normalize_date(feed["feed_date"]),
        "growth": normalize_date(growth["sampling_date"]),
        "water_quality": normalize_date(water["measurement_date"]),
    }

    days_since_feed = max(0, (date.today() - source_dates["feed"]).days)

    return inputs, source_dates, days_since_feed


def find_stale_sources(source_dates: dict) -> dict:
    today = date.today()
    return {
        name: {
            "last_record_date": record_date.isoformat(),
            "age_days": (today - record_date).days,
        }
        for name, record_date in source_dates.items()
        if (today - record_date).days > 7
    }


def build_forecast(db: Session, farm_id: int, pond_number: int) -> dict:
    info = get_pond_in_farm(db, farm_id, pond_number)
    inputs, source_dates, days_since_feed = load_latest_inputs(
        db, info["pond_id"]
    )
    today = date.today()

    daily_forecast = []
    previous_feed = float(inputs["previous_feed_kg"])

    for day_number in range(1, 8):
        prediction_inputs = {
            "doc": int(inputs["doc"]) + days_since_feed + day_number,
            "avg_weight_g": float(inputs["avg_weight_g"]),
            "biomass_kg": float(inputs["biomass_kg"]),
            "temperature_c": float(inputs["temperature_c"]),
            "dissolved_oxygen": float(inputs["dissolved_oxygen"]),
            "previous_feed_kg": previous_feed,
        }

        predicted_kg = run_prediction(prediction_inputs)

        daily_forecast.append({
            "day": day_number,
            "date": (today + timedelta(days=day_number)).isoformat(),
            "doc": prediction_inputs["doc"],
            "predicted_feed_kg": predicted_kg,
        })

        previous_feed = predicted_kg

    return {
        **info,
        "historical_feed_kg": round(float(inputs["previous_feed_kg"]), 2),
        "predicted_feed_kg": daily_forecast[0]["predicted_feed_kg"],  # tomorrow
        "forecast_days": 7,
        "daily_forecast": daily_forecast,
        "total_predicted_feed_kg": round(
            sum(row["predicted_feed_kg"] for row in daily_forecast), 2
        ),
        "source_dates": {
            name: value.isoformat() for name, value in source_dates.items()
        },
        "stale_sources_over_7_days": find_stale_sources(source_dates),
        "assumptions": [
            "Latest growth and water-quality measurements are held constant.",
            "Each predicted feed value becomes the next day's previous-feed input.",
            "This is an experimental recursive forecast, not a validated seven-day model.",
        ],
        "note": (
            "Estimated from the latest feed, growth and water-quality "
            "records. Not yet a validated optimal feeding recommendation."
        ),
    }


@router.post("/")
def predict_single_feed(request: FeedPredictionRequest):
    inputs = request.model_dump()
    predicted_feed_kg = run_prediction(inputs)

    return {
        "predicted_feed_kg": predicted_feed_kg,
        "inputs_used": inputs,
        "message": "Single feed quantity prediction completed.",
    }


# Dropdown data (hidden from Swagger). Pond "id" = pond number 1..N inside the farm.
@router.get("/farms", include_in_schema=False)
def list_farms_with_ponds(db: Session = Depends(get_db)):
    try:
        rows = db.execute(
            text("""
                SELECT f.farm_id,
                       f.farm_name,
                       p.pond_id,
                       p.pond_code,
                       ROW_NUMBER() OVER (
                           PARTITION BY f.farm_id ORDER BY p.pond_id
                       ) AS pond_number
                FROM farms f
                JOIN ponds p ON p.farm_id = f.farm_id
                ORDER BY f.farm_id, p.pond_id
            """)
        ).mappings().all()
    except SQLAlchemyError as exc:
        db_error(db, exc, "list_farms_with_ponds")

    farms = {}
    for r in rows:
        farm = farms.setdefault(
            r["farm_id"],
            {"id": r["farm_id"], "name": r["farm_name"], "ponds": []},
        )
        farm["ponds"].append({
            "id": r["pond_number"],      # pond number (sent in the URL)
            "number": r["pond_number"],
            "db_id": r["pond_id"],       # real DB pond_id (reference only)
            "code": r["pond_code"],
            "label": f"Pond {r['pond_number']}",
        })
    return list(farms.values())


# Old weekly URL kept so WeeklyFeedForecast.jsx keeps working (hidden from Swagger).
@router.get("/weekly/{farm_id}/{pond_number}", include_in_schema=False)
def weekly_feed_forecast(
    farm_id: int,
    pond_number: int,
    db: Session = Depends(get_db),
):
    return build_forecast(db, farm_id, pond_number)


# The ONLY visible GET in Swagger.
# GET /api/feed-prediction/{farm_id}/{pond_number}
@router.get("/{farm_id}/{pond_number}")
def feed_prediction(
    farm_id: int,
    pond_number: int,
    db: Session = Depends(get_db),
):
    return build_forecast(db, farm_id, pond_number)