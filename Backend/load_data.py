import psycopg2
import pandas as pd
from pathlib import Path

DB_CONFIG = {
    "host": "localhost",
    "database": "aquallm",
    "user": "postgres",
    "password": "Dell@123",
    "port": 5432
}

DATA_DIR = Path("../data")

conn = psycopg2.connect(**DB_CONFIG)
cursor = conn.cursor()

print("Connected to PostgreSQL")


# -----------------------------
# 1. Farms
# -----------------------------

farms_df = pd.read_csv(DATA_DIR / "farms.csv")

for _, row in farms_df.iterrows():

    cursor.execute("""
        INSERT INTO farms
        (farm_id, farm_name, location, farm_area_acres, created_at)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        int(row["farm_id"]),
        row["farm_name"],
        row["location"],
        float(row["farm_area_acres"]),
        row["created_at"]
    ))


# -----------------------------
# 2. Ponds
# -----------------------------

ponds_df = pd.read_csv(DATA_DIR / "ponds.csv")

for _, row in ponds_df.iterrows():

    cursor.execute("""
        INSERT INTO ponds
        (pond_id, farm_id, pond_code, area_acres,
         culture_type, status)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        int(row["pond_id"]),
        int(row["farm_id"]),
        row["pond_code"],
        float(row["area_acres"]),
        row["culture_type"],
        row["status"]
    ))


# -----------------------------
# 3. Stocking
# -----------------------------

stocking_df = pd.read_csv(
    DATA_DIR / "stocking_records.csv"
)

for _, row in stocking_df.iterrows():

    cursor.execute("""
        INSERT INTO stocking_records
        (pond_id, stocking_date, species,
         seed_count, avg_seed_weight_g, stocking_density)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        int(row["pond_id"]),
        row["stocking_date"],
        row["species"],
        int(row["seed_count"]),
        float(row["avg_seed_weight_g"]),
        float(row["stocking_density"])
    ))


# -----------------------------
# 4. Feed
# -----------------------------

feed_df = pd.read_csv(
    DATA_DIR / "feed_records.csv"
)

for _, row in feed_df.iterrows():

    cursor.execute("""
        INSERT INTO feed_records
        (pond_id, feed_date, doc,
         feed_type, feed_quantity_kg, feeding_frequency)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (
        int(row["pond_id"]),
        row["feed_date"],
        int(row["doc"]),
        row["feed_type"],
        float(row["feed_quantity_kg"]),
        int(row["feeding_frequency"])
    ))


# -----------------------------
# 5. Water Quality
# -----------------------------

water_df = pd.read_csv(
    DATA_DIR / "water_quality.csv"
)

for _, row in water_df.iterrows():

    cursor.execute("""
        INSERT INTO water_quality
        (pond_id, measurement_date, doc,
         temperature_c, ph, dissolved_oxygen,
         salinity_ppt, ammonia_mg_l)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        int(row["pond_id"]),
        row["measurement_date"],
        int(row["doc"]),
        float(row["temperature_c"]),
        float(row["ph"]),
        float(row["dissolved_oxygen"]),
        float(row["salinity_ppt"]),
        float(row["ammonia_mg_l"])
    ))


# -----------------------------
# 6. Growth Sampling
# -----------------------------

growth_df = pd.read_csv(
    DATA_DIR / "growth_sampling.csv"
)

for _, row in growth_df.iterrows():

    cursor.execute("""
        INSERT INTO growth_sampling
        (pond_id, sampling_date, doc,
         avg_weight_g, biomass_kg,
         adg_g, estimated_survival_pct)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        int(row["pond_id"]),
        row["sampling_date"],
        int(row["doc"]),
        float(row["avg_weight_g"]),
        float(row["biomass_kg"]),
        float(row["adg_g"]),
        float(row["estimated_survival_pct"])
    ))


# -----------------------------
# 7. Harvest
# -----------------------------

harvest_df = pd.read_csv(
    DATA_DIR / "harvest_records.csv"
)

for _, row in harvest_df.iterrows():

    cursor.execute("""
        INSERT INTO harvest_records
        (pond_id, harvest_date,
         harvest_quantity_kg,
         avg_weight_g,
         survival_pct,
         total_feed_kg,
         fcr)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        int(row["pond_id"]),
        row["harvest_date"],
        float(row["harvest_quantity_kg"]),
        float(row["avg_weight_g"]),
        float(row["survival_pct"]),
        float(row["total_feed_kg"]),
        float(row["fcr"])
    ))


conn.commit()

cursor.close()
conn.close()

print("================================")
print("AquaLLM data loaded successfully")
print("================================")