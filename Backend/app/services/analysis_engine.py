# app/services/analysis_engine.py

from typing import Optional, Dict, Any, List

from sqlalchemy import text
from sqlalchemy.orm import Session


# ============================================================
# POND IDENTIFICATION
# ============================================================

def find_analysis_pond(
    question: str,
    db: Session
) -> Dict[str, Any]:

    q = question.upper().strip()

    # --------------------------------------------------------
    # 1. Try exact full pond code
    # Example: F01-P03
    # --------------------------------------------------------

    import re

    full_code_match = re.search(
        r"\bF\d{2}-P\d{2}\b",
        q
    )

    if full_code_match:

        pond_code = full_code_match.group(0)

        query = text("""
            SELECT
                pond_id,
                pond_code,
                farm_id,
                area_acres,
                culture_type,
                status
            FROM ponds
            WHERE UPPER(pond_code) = :pond_code
            LIMIT 1
        """)

        result = db.execute(
            query,
            {"pond_code": pond_code}
        ).mappings().first()

        if result:

            return {
                "status": "found",
                "pond": dict(result)
            }

    # --------------------------------------------------------
    # 2. Try short pond code
    # Example: P03
    #
    # There can be:
    # F01-P03
    # F02-P03
    # F03-P03
    # etc.
    #
    # Therefore DO NOT randomly select one.
    # --------------------------------------------------------

    short_code_match = re.search(
        r"\bP\d{1,2}\b",
        q
    )

    if short_code_match:

        short_code = short_code_match.group(0)

        query = text("""
            SELECT
                pond_id,
                pond_code,
                farm_id,
                area_acres,
                culture_type,
                status
            FROM ponds
            WHERE UPPER(pond_code) LIKE :pattern
            ORDER BY pond_id
        """)

        results = db.execute(
            query,
            {
                "pattern": f"%-{short_code}"
            }
        ).mappings().all()

        ponds = [dict(row) for row in results]

        if len(ponds) == 1:

            return {
                "status": "found",
                "pond": ponds[0]
            }

        if len(ponds) > 1:

            return {
                "status": "ambiguous",
                "short_code": short_code,
                "ponds": ponds
            }

    # --------------------------------------------------------
    # 3. Try pond ID
    #
    # Example:
    # "pond 3"
    # "pond id 3"
    # --------------------------------------------------------

    pond_id_match = re.search(
        r"\b(?:POND\s*(?:ID)?\s*[:#-]?\s*)(\d+)\b",
        q
    )

    if pond_id_match:

        pond_id = int(
            pond_id_match.group(1)
        )

        query = text("""
            SELECT
                pond_id,
                pond_code,
                farm_id,
                area_acres,
                culture_type,
                status
            FROM ponds
            WHERE pond_id = :pond_id
            LIMIT 1
        """)

        result = db.execute(
            query,
            {"pond_id": pond_id}
        ).mappings().first()

        if result:

            return {
                "status": "found",
                "pond": dict(result)
            }

    # --------------------------------------------------------
    # Pond not found
    # --------------------------------------------------------

    return {
        "status": "not_found"
    }


# ============================================================
# QUESTION TYPE DETECTION
# ============================================================

def detect_analysis_type(question: str) -> Optional[str]:

    q = question.lower().strip()

    # --------------------------------------------------------
    # 1. ABW TREND
    # --------------------------------------------------------

    if (
        (
            "abw" in q
            or "average body weight" in q
            or "average weight" in q
            or "body weight" in q
        )
        and
        any(
            word in q
            for word in [
                "trend",
                "history",
                "over time",
                "progress",
                "change",
                "growth trend"
            ]
        )
    ):
        return "abw_trend"

    # --------------------------------------------------------
    # 2. GENERAL GROWTH TREND
    # --------------------------------------------------------

    if (
        "growth" in q
        and any(
            word in q
            for word in [
                "trend",
                "history",
                "over time",
                "progress"
            ]
        )
    ):
        return "growth_trend"

    # --------------------------------------------------------
    # 3. WATER QUALITY TREND
    # --------------------------------------------------------

    if (
        (
            "water quality" in q
            or "water parameter" in q
            or "water parameters" in q
        )
        and
        any(
            word in q
            for word in [
                "trend",
                "history",
                "over time",
                "change"
            ]
        )
    ):
        return "water_trend"

    # --------------------------------------------------------
    # 4. DO TREND
    # --------------------------------------------------------

    if (
        (
            "do" in q
            or "dissolved oxygen" in q
        )
        and
        any(
            word in q
            for word in [
                "trend",
                "history",
                "over time",
                "change"
            ]
        )
    ):
        return "do_trend"

    # --------------------------------------------------------
    # 5. TEMPERATURE TREND
    # --------------------------------------------------------

    if (
        (
            "temperature" in q
            or "temp" in q
        )
        and
        any(
            word in q
            for word in [
                "trend",
                "history",
                "over time",
                "change"
            ]
        )
    ):
        return "temperature_trend"

    # --------------------------------------------------------
    # 6. PH TREND
    # --------------------------------------------------------

    if (
        (
            "ph" in q
            or "pH".lower() in q
        )
        and
        any(
            word in q
            for word in [
                "trend",
                "history",
                "over time",
                "change"
            ]
        )
    ):
        return "ph_trend"

    # --------------------------------------------------------
    # 7. GROWTH DIAGNOSIS
    #
    # Example:
    # "Why is growth slow in F01-P03?"
    # "Is there a problem with growth?"
    # --------------------------------------------------------

    if (
        "growth" in q
        and
        any(
            word in q
            for word in [
                "why",
                "slow",
                "problem",
                "issue",
                "reason",
                "poor",
                "bad"
            ]
        )
    ):
        return "growth_analysis"

    return None


# ============================================================
# ABW TREND
# ============================================================

def get_abw_trend(
    pond_id: int,
    pond_code: str,
    db: Session
) -> Dict[str, Any]:

    query = text("""
        SELECT
            sampling_date,
            doc,
            avg_weight_g,
            adg_g,
            biomass_kg,
            estimated_survival_pct
        FROM growth_sampling
        WHERE pond_id = :pond_id
        ORDER BY doc ASC, sampling_date ASC
    """)

    rows = db.execute(
        query,
        {"pond_id": pond_id}
    ).mappings().all()

    data = []

    for row in rows:

        data.append({
            "doc": row["doc"],
            "date": (
                row["sampling_date"].isoformat()
                if row["sampling_date"]
                else None
            ),
            "abw": float(row["avg_weight_g"])
            if row["avg_weight_g"] is not None
            else None,
            "adg": float(row["adg_g"])
            if row["adg_g"] is not None
            else None,
            "biomass": float(row["biomass_kg"])
            if row["biomass_kg"] is not None
            else None,
            "survival": float(row["estimated_survival_pct"])
            if row["estimated_survival_pct"] is not None
            else None
        })

    latest = data[-1] if data else None

    latest_text = ""

    if latest:
        latest_text = (
            f"The latest ABW is {latest['abw']} g "
            f"at DOC {latest['doc']}."
        )

    return {
        "type": "chart",
        "response": (
            f"Here is the ABW trend for {pond_code}. "
            + latest_text
        ),
        "chart": {
            "chart_type": "line",
            "title": f"ABW Trend - {pond_code}",
            "x_axis": "DOC",
            "y_axis": "ABW (g)",
            "data": data
        }
    }


# ============================================================
# GENERAL GROWTH TREND
# ============================================================

def get_growth_trend(
    pond_id: int,
    pond_code: str,
    db: Session
) -> Dict[str, Any]:

    query = text("""
        SELECT
            sampling_date,
            doc,
            avg_weight_g,
            adg_g,
            biomass_kg,
            estimated_survival_pct
        FROM growth_sampling
        WHERE pond_id = :pond_id
        ORDER BY doc ASC, sampling_date ASC
    """)

    rows = db.execute(
        query,
        {"pond_id": pond_id}
    ).mappings().all()

    data = []

    for row in rows:

        data.append({
            "doc": row["doc"],
            "date": (
                row["sampling_date"].isoformat()
                if row["sampling_date"]
                else None
            ),
            "abw": float(row["avg_weight_g"])
            if row["avg_weight_g"] is not None
            else None,
            "adg": float(row["adg_g"])
            if row["adg_g"] is not None
            else None,
            "biomass": float(row["biomass_kg"])
            if row["biomass_kg"] is not None
            else None,
            "survival": float(row["estimated_survival_pct"])
            if row["estimated_survival_pct"] is not None
            else None
        })

    return {
        "type": "chart",
        "response": (
            f"Here is the growth trend for {pond_code}, "
            f"including ABW, ADG, biomass and survival."
        ),
        "chart": {
            "chart_type": "line",
            "title": f"Growth Trend - {pond_code}",
            "x_axis": "DOC",
            "y_axis": "Growth Metrics",
            "data": data
        }
    }


# ============================================================
# WATER QUALITY TREND
# ============================================================

def get_water_trend(
    pond_id: int,
    pond_code: str,
    db: Session
) -> Dict[str, Any]:

    query = text("""
        SELECT
            measurement_date,
            doc,
            temperature_c,
            ph,
            dissolved_oxygen,
            salinity_ppt,
            ammonia_mg_l
        FROM water_quality
        WHERE pond_id = :pond_id
        ORDER BY doc ASC, measurement_date ASC
    """)

    rows = db.execute(
        query,
        {"pond_id": pond_id}
    ).mappings().all()

    data = []

    for row in rows:

        data.append({
            "doc": row["doc"],
            "date": (
                row["measurement_date"].isoformat()
                if row["measurement_date"]
                else None
            ),
            "temperature": float(row["temperature_c"])
            if row["temperature_c"] is not None
            else None,
            "ph": float(row["ph"])
            if row["ph"] is not None
            else None,
            "do": float(row["dissolved_oxygen"])
            if row["dissolved_oxygen"] is not None
            else None,
            "salinity": float(row["salinity_ppt"])
            if row["salinity_ppt"] is not None
            else None,
            "ammonia": float(row["ammonia_mg_l"])
            if row["ammonia_mg_l"] is not None
            else None
        })

    return {
        "type": "chart",
        "response": (
            f"Here is the water-quality trend for {pond_code}. "
            "The chart contains temperature, pH, DO, salinity and ammonia."
        ),
        "chart": {
            "chart_type": "multi_line",
            "title": f"Water Quality Trend - {pond_code}",
            "x_axis": "DOC",
            "y_axis": "Water Quality",
            "data": data
        }
    }


# ============================================================
# DO TREND
# ============================================================

def get_do_trend(
    pond_id: int,
    pond_code: str,
    db: Session
) -> Dict[str, Any]:

    query = text("""
        SELECT
            measurement_date,
            doc,
            dissolved_oxygen
        FROM water_quality
        WHERE pond_id = :pond_id
        ORDER BY doc ASC, measurement_date ASC
    """)

    rows = db.execute(
        query,
        {"pond_id": pond_id}
    ).mappings().all()

    data = []

    for row in rows:

        data.append({
            "doc": row["doc"],
            "date": (
                row["measurement_date"].isoformat()
                if row["measurement_date"]
                else None
            ),
            "do": float(row["dissolved_oxygen"])
            if row["dissolved_oxygen"] is not None
            else None
        })

    latest = data[-1] if data else None

    latest_text = ""

    if latest:
        latest_text = (
            f"The latest DO value is {latest['do']} mg/L "
            f"at DOC {latest['doc']}."
        )

    return {
        "type": "chart",
        "response": (
            f"Here is the DO trend for {pond_code}. "
            + latest_text
        ),
        "chart": {
            "chart_type": "line",
            "title": f"DO Trend - {pond_code}",
            "x_axis": "DOC",
            "y_axis": "DO (mg/L)",
            "data": data
        }
    }


# ============================================================
# TEMPERATURE TREND
# ============================================================

def get_temperature_trend(
    pond_id: int,
    pond_code: str,
    db: Session
) -> Dict[str, Any]:

    query = text("""
        SELECT
            measurement_date,
            doc,
            temperature_c
        FROM water_quality
        WHERE pond_id = :pond_id
        ORDER BY doc ASC, measurement_date ASC
    """)

    rows = db.execute(
        query,
        {"pond_id": pond_id}
    ).mappings().all()

    data = []

    for row in rows:

        data.append({
            "doc": row["doc"],
            "date": (
                row["measurement_date"].isoformat()
                if row["measurement_date"]
                else None
            ),
            "temperature": float(row["temperature_c"])
            if row["temperature_c"] is not None
            else None
        })

    return {
        "type": "chart",
        "response": (
            f"Here is the temperature trend for {pond_code}."
        ),
        "chart": {
            "chart_type": "line",
            "title": f"Temperature Trend - {pond_code}",
            "x_axis": "DOC",
            "y_axis": "Temperature (°C)",
            "data": data
        }
    }


# ============================================================
# PH TREND
# ============================================================

def get_ph_trend(
    pond_id: int,
    pond_code: str,
    db: Session
) -> Dict[str, Any]:

    query = text("""
        SELECT
            measurement_date,
            doc,
            ph
        FROM water_quality
        WHERE pond_id = :pond_id
        ORDER BY doc ASC, measurement_date ASC
    """)

    rows = db.execute(
        query,
        {"pond_id": pond_id}
    ).mappings().all()

    data = []

    for row in rows:

        data.append({
            "doc": row["doc"],
            "date": (
                row["measurement_date"].isoformat()
                if row["measurement_date"]
                else None
            ),
            "ph": float(row["ph"])
            if row["ph"] is not None
            else None
        })

    return {
        "type": "chart",
        "response": (
            f"Here is the pH trend for {pond_code}."
        ),
        "chart": {
            "chart_type": "line",
            "title": f"pH Trend - {pond_code}",
            "x_axis": "DOC",
            "y_axis": "pH",
            "data": data
        }
    }


# ============================================================
# MAIN ANALYSIS ROUTER
# ============================================================

def analyze_question(
    question: str,
    db: Session
) -> Optional[Dict[str, Any]]:

    analysis_type = detect_analysis_type(question)

    # --------------------------------------------------------
    # If question is not an analysis/chart question
    # return None so chatbot.py handles it.
    # --------------------------------------------------------

    if analysis_type is None:
        return None

    # --------------------------------------------------------
    # Growth diagnosis is handled by chat.py
    # because it uses growth_analysis.py
    # --------------------------------------------------------

    if analysis_type == "growth_analysis":
        return None

    # --------------------------------------------------------
    # Identify pond
    # --------------------------------------------------------

    pond_result = find_analysis_pond(
        question,
        db
    )

    # --------------------------------------------------------
    # Ambiguous pond
    # --------------------------------------------------------

    if pond_result["status"] == "ambiguous":

        codes = [
            pond["pond_code"]
            for pond in pond_result["ponds"]
        ]

        return {
            "type": "text",
            "response": (
                f"Multiple ponds match "
                f"{pond_result['short_code']}: "
                + ", ".join(codes)
                + ". Please specify the complete pond code."
            ),
            "chart": None
        }

    # --------------------------------------------------------
    # Pond not found
    # --------------------------------------------------------

    if pond_result["status"] == "not_found":

        return {
            "type": "text",
            "response": (
                "I could not identify the pond. "
                "Please provide the complete pond code, "
                "for example F01-P03."
            ),
            "chart": None
        }

    # --------------------------------------------------------
    # Pond found
    # --------------------------------------------------------

    pond = pond_result["pond"]

    pond_id = pond["pond_id"]
    pond_code = pond["pond_code"]

    # --------------------------------------------------------
    # Select analysis
    # --------------------------------------------------------

    if analysis_type == "abw_trend":

        return get_abw_trend(
            pond_id,
            pond_code,
            db
        )

    if analysis_type == "growth_trend":

        return get_growth_trend(
            pond_id,
            pond_code,
            db
        )

    if analysis_type == "water_trend":

        return get_water_trend(
            pond_id,
            pond_code,
            db
        )

    if analysis_type == "do_trend":

        return get_do_trend(
            pond_id,
            pond_code,
            db
        )

    if analysis_type == "temperature_trend":

        return get_temperature_trend(
            pond_id,
            pond_code,
            db
        )

    if analysis_type == "ph_trend":

        return get_ph_trend(
            pond_id,
            pond_code,
            db
        )

    return None