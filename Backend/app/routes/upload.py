from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
import pandas as pd
import io


router = APIRouter(
    prefix="/api/upload",
    tags=["CSV / Excel Upload"]
)


# ============================================================
# SUPPORTED TABLES
# ============================================================

TABLE_CONFIG = {

    "farms": {
        "table": "farms",
        "columns": [
            "farm_name",
            "location",
            "farm_area_acres",
            "created_at"
        ],
        "id_column": "farm_id"
    },

    "ponds": {
        "table": "ponds",
        "columns": [
            "farm_id",
            "pond_code",
            "area_acres",
            "culture_type",
            "status"
        ],
        "id_column": "pond_id"
    },

    "feed_records": {
        "table": "feed_records",
        "columns": [
            "pond_id",
            "feed_date",
            "doc",
            "feed_type",
            "feed_quantity_kg",
            "feeding_frequency"
        ],
        "id_column": "feed_id"
    },

    "water_quality": {
        "table": "water_quality",
        "columns": [
            "pond_id",
            "measurement_date",
            "doc",
            "temperature_c",
            "ph",
            "dissolved_oxygen",
            "salinity_ppt",
            "ammonia_mg_l"
        ],
        "id_column": "water_id"
    },

    "growth_sampling": {
        "table": "growth_sampling",
        "columns": [
            "pond_id",
            "sampling_date",
            "doc",
            "avg_weight_g",
            "biomass_kg",
            "adg_g",
            "estimated_survival_pct"
        ],
        "id_column": "sampling_id"
    },

    "harvest_records": {
        "table": "harvest_records",
        "columns": [
            "pond_id",
            "harvest_date",
            "harvest_quantity_kg",
            "avg_weight_g",
            "survival_pct",
            "total_feed_kg",
            "fcr"
        ],
        "id_column": "harvest_id"
    },

    "stocking_records": {
        "table": "stocking_records",
        "columns": [
            "pond_id",
            "stocking_date",
            "species",
            "seed_count",
            "avg_seed_weight_g",
            "stocking_density"
        ],
        "id_column": "stocking_id"
    }
}


# ============================================================
# DATABASE
# ============================================================

from app.database import get_db


# ============================================================
# READ CSV / EXCEL
# ============================================================

def read_uploaded_file(contents: bytes, filename: str):

    filename_lower = filename.lower()

    try:

        if filename_lower.endswith(".csv"):

            df = pd.read_csv(
                io.BytesIO(contents)
            )

        elif filename_lower.endswith(".xlsx"):

            df = pd.read_excel(
                io.BytesIO(contents),
                engine="openpyxl"
            )

        elif filename_lower.endswith(".xls"):

            df = pd.read_excel(
                io.BytesIO(contents)
            )

        else:

            raise HTTPException(
                status_code=400,
                detail="Only CSV, XLSX and XLS files are supported."
            )

        return df

    except HTTPException:
        raise

    except Exception as e:

        raise HTTPException(
            status_code=400,
            detail=f"Unable to read file: {str(e)}"
        )


# ============================================================
# CLEAN VALUES
# ============================================================

def clean_dataframe(df):

    # Remove completely empty rows
    df = df.dropna(
        how="all"
    )

    # Remove spaces from column names
    df.columns = [
        str(column).strip()
        for column in df.columns
    ]

    # Convert NaN to None
    df = df.where(
        pd.notnull(df),
        None
    )

    return df


# ============================================================
# UPLOAD
# ============================================================

@router.post("/{table_name}")
async def upload_data(
    table_name: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):

    # --------------------------------------------------------
    # Check table
    # --------------------------------------------------------

    if table_name not in TABLE_CONFIG:

        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported table '{table_name}'. "
                f"Supported tables: "
                f"{', '.join(TABLE_CONFIG.keys())}"
            )
        )


    config = TABLE_CONFIG[table_name]

    table = config["table"]

    expected_columns = config["columns"]

    id_column = config["id_column"]


    # --------------------------------------------------------
    # Check filename
    # --------------------------------------------------------

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="No file selected."
        )


    filename = file.filename.lower()


    if not (
        filename.endswith(".csv")
        or filename.endswith(".xlsx")
        or filename.endswith(".xls")
    ):

        raise HTTPException(
            status_code=400,
            detail="Upload a CSV or Excel file."
        )


    # --------------------------------------------------------
    # Read file
    # --------------------------------------------------------

    contents = await file.read()

    if not contents:

        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty."
        )


    df = read_uploaded_file(
        contents,
        file.filename
    )


    # --------------------------------------------------------
    # Clean
    # --------------------------------------------------------

    df = clean_dataframe(df)


    if df.empty:

        raise HTTPException(
            status_code=400,
            detail="The uploaded file contains no data."
        )


    # --------------------------------------------------------
    # Check columns
    # --------------------------------------------------------

    uploaded_columns = list(df.columns)


    # Allow the primary key to be present,
    # but we do not insert it.

    allowed_columns = expected_columns + [id_column]

    unexpected_columns = [
        column
        for column in uploaded_columns
        if column not in allowed_columns
    ]


    if unexpected_columns:

        raise HTTPException(
            status_code=400,
            detail={
                "message": "Unexpected columns found.",
                "unexpected_columns": unexpected_columns,
                "expected_columns": expected_columns
            }
        )


    missing_columns = [
        column
        for column in expected_columns
        if column not in uploaded_columns
    ]


    if missing_columns:

        raise HTTPException(
            status_code=400,
            detail={
                "message": "Required columns are missing.",
                "missing_columns": missing_columns,
                "expected_columns": expected_columns
            }
        )


    # --------------------------------------------------------
    # Keep only required columns
    # --------------------------------------------------------

    df = df[
        expected_columns
    ]


    # --------------------------------------------------------
    # Convert date columns
    # --------------------------------------------------------

    date_columns = {

        "farms": [
            "created_at"
        ],

        "ponds": [],

        "feed_records": [
            "feed_date"
        ],

        "water_quality": [
            "measurement_date"
        ],

        "growth_sampling": [
            "sampling_date"
        ],

        "harvest_records": [
            "harvest_date"
        ],

        "stocking_records": [
            "stocking_date"
        ]

    }


    for column in date_columns.get(
        table_name,
        []
    ):

        df[column] = pd.to_datetime(
            df[column],
            errors="coerce"
        ).dt.date


    # --------------------------------------------------------
    # Validate dates
    # --------------------------------------------------------

    for column in date_columns.get(
        table_name,
        []
    ):

        invalid_dates = df[column].isna().sum()

        if invalid_dates > 0:

            raise HTTPException(
                status_code=400,
                detail=(
                    f"Invalid or missing dates found "
                    f"in column '{column}'. "
                    f"Rows affected: {invalid_dates}"
                )
            )


    # --------------------------------------------------------
    # Insert rows
    # --------------------------------------------------------

    inserted_count = 0


    try:

        for _, row in df.iterrows():

            values = {}

            for column in expected_columns:

                value = row[column]

                # Convert pandas values to Python values
                if pd.isna(value):
                    value = None

                values[column] = value


            column_string = ", ".join(
                expected_columns
            )


            parameter_string = ", ".join(
                f":{column}"
                for column in expected_columns
            )


            query = text(
                f"""
                INSERT INTO {table}
                ({column_string})
                VALUES
                ({parameter_string})
                """
            )


            db.execute(
                query,
                values
            )


            inserted_count += 1


        db.commit()


    except Exception as e:

        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=(
                "Database insertion failed: "
                f"{str(e)}"
            )
        )


    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    return {

        "message": "File uploaded successfully",

        "table": table,

        "filename": file.filename,

        "rows_uploaded": inserted_count,

        "columns": expected_columns

    }