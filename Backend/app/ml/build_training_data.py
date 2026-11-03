
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

from app.config import DATABASE_URL


# ============================================================
# DATABASE CONNECTION
# Uses the existing AquaLLM database configuration
# ============================================================

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


# ============================================================
# SQL QUERY
# Combines feeding records with the latest available
# growth and water-quality measurements for each pond.
# Measurements are selected from the feeding date or earlier.
# ============================================================

QUERY = text("""
WITH daily_feed AS (
    SELECT
        pond_id,
        feed_date::date AS feed_date,
        MAX(doc) AS doc,
        SUM(feed_quantity_kg) AS feed_quantity_kg
    FROM feed_records
    GROUP BY pond_id, feed_date::date
)

SELECT
    f.pond_id,
    f.feed_date,
    f.doc,
    f.feed_quantity_kg,

    (
        SELECT g.avg_weight_g
        FROM growth_sampling AS g
        WHERE g.pond_id = f.pond_id
          AND g.sampling_date::date <= f.feed_date
        ORDER BY g.sampling_date DESC
        LIMIT 1
    ) AS avg_weight_g,

    (
        SELECT g.biomass_kg
        FROM growth_sampling AS g
        WHERE g.pond_id = f.pond_id
          AND g.sampling_date::date <= f.feed_date
        ORDER BY g.sampling_date DESC
        LIMIT 1
    ) AS biomass_kg,

    (
        SELECT w.temperature_c
        FROM water_quality AS w
        WHERE w.pond_id = f.pond_id
          AND w.measurement_date::date <= f.feed_date
        ORDER BY w.measurement_date DESC
        LIMIT 1
    ) AS temperature_c,

    (
        SELECT w.dissolved_oxygen
        FROM water_quality AS w
        WHERE w.pond_id = f.pond_id
          AND w.measurement_date::date <= f.feed_date
        ORDER BY w.measurement_date DESC
        LIMIT 1
    ) AS dissolved_oxygen

FROM daily_feed AS f
ORDER BY f.pond_id, f.feed_date
""")


# ============================================================
# BUILD TRAINING DATA
# ============================================================

def main():
    print("Connecting to AquaLLM PostgreSQL database...")

    try:
        with engine.connect() as connection:
            # Verify database connection
            connection.execute(text("SELECT 1"))

            print("Database connection successful.")
            print("Fetching feed, growth, and water-quality records...")

            data = pd.read_sql_query(QUERY, connection)

    except Exception as exc:
        print("\nFailed to retrieve training data.")
        print("Check the database configuration and table columns.")
        print(f"Error: {exc}")
        raise

    if data.empty:
        raise ValueError(
            "No feeding records were found. "
            "Check the feed_records table."
        )

    # Ensure records are sorted chronologically for each pond.
    data["feed_date"] = pd.to_datetime(data["feed_date"])

    data = data.sort_values(
        ["pond_id", "feed_date"]
    ).reset_index(drop=True)

    # Previous recorded feeding quantity for the same pond.
    data["previous_feed_kg"] = (
        data.groupby("pond_id")["feed_quantity_kg"].shift(1)
    )

    # Remove rows that have no target value.
    data = data.dropna(
        subset=["feed_quantity_kg"]
    )

    # Save the generated dataset inside app/ml/.
    output_path = (
        Path(__file__).resolve().parent
        / "feed_training_data.csv"
    )

    data.to_csv(output_path, index=False)

    print("\nTraining dataset created successfully!")
    print(f"Rows saved: {len(data)}")
    print(f"Ponds included: {data['pond_id'].nunique()}")
    print(f"Output file: {output_path}")

    print("\nAvailable columns:")
    for column in data.columns:
        print(f"- {column}")

    print("\nMissing values:")
    print(data.isnull().sum().to_string())


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
