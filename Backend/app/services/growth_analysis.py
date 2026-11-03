from sqlalchemy import text
from sqlalchemy.orm import Session


# ============================================================
# GET LATEST GROWTH
# ============================================================

def get_latest_growth(
    pond_id: int,
    db: Session
):

    result = db.execute(
        text("""
            SELECT
                sampling_date,
                doc,
                avg_weight_g,
                biomass_kg,
                adg_g,
                estimated_survival_pct
            FROM growth_sampling
            WHERE pond_id = :pond_id
            ORDER BY sampling_date DESC
            LIMIT 1
        """),
        {
            "pond_id": pond_id
        }
    )

    row = result.fetchone()

    if row is None:
        return None

    return dict(row._mapping)


# ============================================================
# GET PREVIOUS GROWTH
# ============================================================

def get_previous_growth(
    pond_id: int,
    db: Session
):

    result = db.execute(
        text("""
            SELECT
                sampling_date,
                doc,
                avg_weight_g,
                biomass_kg,
                adg_g,
                estimated_survival_pct
            FROM growth_sampling
            WHERE pond_id = :pond_id
            ORDER BY sampling_date DESC
            OFFSET 1
            LIMIT 1
        """),
        {
            "pond_id": pond_id
        }
    )

    row = result.fetchone()

    if row is None:
        return None

    return dict(row._mapping)


# ============================================================
# GET LATEST WATER QUALITY
# ============================================================

def get_latest_water(
    pond_id: int,
    db: Session
):

    result = db.execute(
        text("""
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
            ORDER BY measurement_date DESC
            LIMIT 1
        """),
        {
            "pond_id": pond_id
        }
    )

    row = result.fetchone()

    if row is None:
        return None

    return dict(row._mapping)


# ============================================================
# GET RECENT FEED
# ============================================================

def get_recent_feed(
    pond_id: int,
    db: Session
):

    result = db.execute(
        text("""
            SELECT
                feed_date,
                doc,
                feed_type,
                feed_quantity_kg,
                feeding_frequency
            FROM feed_records
            WHERE pond_id = :pond_id
            ORDER BY feed_date DESC
            LIMIT 5
        """),
        {
            "pond_id": pond_id
        }
    )

    return [
        dict(row._mapping)
        for row in result
    ]


# ============================================================
# CALCULATE GROWTH CHANGE
# ============================================================

def calculate_growth_change(
    latest,
    previous
):

    if not latest or not previous:
        return None

    latest_abw = float(
        latest["avg_weight_g"]
    )

    previous_abw = float(
        previous["avg_weight_g"]
    )

    abw_change = (
        latest_abw -
        previous_abw
    )

    latest_adg = float(
        latest["adg_g"]
    )

    previous_adg = float(
        previous["adg_g"]
    )

    adg_change = (
        latest_adg -
        previous_adg
    )

    return {
        "abw_change": round(
            abw_change,
            2
        ),
        "adg_change": round(
            adg_change,
            3
        )
    }


# ============================================================
# ANALYZE WATER FACTORS
# ============================================================

def analyze_water(
    water
):

    findings = []

    if water is None:

        return findings

    # --------------------------------------------------------
    # DO
    # --------------------------------------------------------

    do = water["dissolved_oxygen"]

    if do is not None:

        do = float(do)

        if do < 4:

            findings.append({
                "factor": "Dissolved Oxygen",
                "value": do,
                "unit": "mg/L",
                "severity": "high",
                "message": (
                    "Dissolved oxygen is low and may "
                    "stress shrimp and affect growth."
                )
            })

        elif do < 5:

            findings.append({
                "factor": "Dissolved Oxygen",
                "value": do,
                "unit": "mg/L",
                "severity": "moderate",
                "message": (
                    "Dissolved oxygen is below the "
                    "preferred level and should be monitored."
                )
            })

    # --------------------------------------------------------
    # pH
    # --------------------------------------------------------

    ph = water["ph"]

    if ph is not None:

        ph = float(ph)

        if ph < 7:

            findings.append({
                "factor": "pH",
                "value": ph,
                "unit": "",
                "severity": "moderate",
                "message": (
                    "pH is relatively low and may "
                    "affect shrimp performance."
                )
            })

        elif ph > 9:

            findings.append({
                "factor": "pH",
                "value": ph,
                "unit": "",
                "severity": "moderate",
                "message": (
                    "pH is relatively high and should "
                    "be monitored."
                )
            })

    # --------------------------------------------------------
    # TEMPERATURE
    # --------------------------------------------------------

    temperature = water["temperature_c"]

    if temperature is not None:

        temperature = float(
            temperature
        )

        if (
            temperature < 26
            or temperature > 32
        ):

            findings.append({
                "factor": "Temperature",
                "value": temperature,
                "unit": "°C",
                "severity": "moderate",
                "message": (
                    "Temperature is outside the "
                    "typical monitoring range."
                )
            })

    # --------------------------------------------------------
    # AMMONIA
    # --------------------------------------------------------

    ammonia = water["ammonia_mg_l"]

    if ammonia is not None:

        ammonia = float(ammonia)

        if ammonia > 0.05:

            findings.append({
                "factor": "Ammonia",
                "value": ammonia,
                "unit": "mg/L",
                "severity": "high",
                "message": (
                    "Ammonia is elevated and may "
                    "stress shrimp."
                )
            })

    return findings


# ============================================================
# ANALYZE GROWTH
# ============================================================

def analyze_growth_metrics(
    latest,
    previous
):

    findings = []

    if latest is None:
        return findings

    adg = latest["adg_g"]

    # --------------------------------------------------------
    # ADG
    # --------------------------------------------------------

    if adg is not None:

        adg = float(adg)

        if adg < 0.20:

            findings.append({
                "factor": "ADG",
                "value": adg,
                "unit": "g/day",
                "severity": "high",
                "message": (
                    "Average Daily Growth is low."
                )
            })

        elif adg < 0.25:

            findings.append({
                "factor": "ADG",
                "value": adg,
                "unit": "g/day",
                "severity": "moderate",
                "message": (
                    "Average Daily Growth is relatively low."
                )
            })

    # --------------------------------------------------------
    # SURVIVAL
    # --------------------------------------------------------

    survival = latest[
        "estimated_survival_pct"
    ]

    if survival is not None:

        survival = float(survival)

        if survival < 80:

            findings.append({
                "factor": "Survival",
                "value": survival,
                "unit": "%",
                "severity": "high",
                "message": (
                    "Estimated survival is low."
                )
            })

        elif survival < 85:

            findings.append({
                "factor": "Survival",
                "value": survival,
                "unit": "%",
                "severity": "moderate",
                "message": (
                    "Estimated survival is below "
                    "the desired level."
                )
            })

    # --------------------------------------------------------
    # ABW CHANGE
    # --------------------------------------------------------

    if previous:

        latest_abw = float(
            latest["avg_weight_g"]
        )

        previous_abw = float(
            previous["avg_weight_g"]
        )

        if latest_abw <= previous_abw:

            findings.append({
                "factor": "ABW",
                "value": latest_abw,
                "unit": "g",
                "severity": "high",
                "message": (
                    "Average Body Weight has not increased "
                    "since the previous sampling."
                )
            })

    return findings


# ============================================================
# MAIN GROWTH ANALYSIS
# ============================================================

def analyze_growth(
    pond_id: int,
    pond_code: str,
    db: Session
):

    latest = get_latest_growth(
        pond_id,
        db
    )

    previous = get_previous_growth(
        pond_id,
        db
    )

    water = get_latest_water(
        pond_id,
        db
    )

    feed = get_recent_feed(
        pond_id,
        db
    )

    # --------------------------------------------------------
    # No growth data
    # --------------------------------------------------------

    if latest is None:

        return {
            "type": "text",
            "response": (
                f"No growth data is available "
                f"for {pond_code}."
            )
        }

    # --------------------------------------------------------
    # Analyze
    # --------------------------------------------------------

    growth_findings = analyze_growth_metrics(
        latest,
        previous
    )

    water_findings = analyze_water(
        water
    )

    findings = (
        growth_findings +
        water_findings
    )

    # --------------------------------------------------------
    # Overall status
    # --------------------------------------------------------

    high_count = sum(
        1
        for finding in findings
        if finding["severity"] == "high"
    )

    moderate_count = sum(
        1
        for finding in findings
        if finding["severity"] == "moderate"
    )

    if high_count > 0:

        status = "Attention Required"

    elif moderate_count > 0:

        status = "Monitor"

    else:

        status = "Normal"

    # --------------------------------------------------------
    # Build summary
    # --------------------------------------------------------

    summary = (
        f"Growth analysis for {pond_code}: "
        f"ABW is {latest['avg_weight_g']} g, "
        f"ADG is {latest['adg_g']} g/day, "
        f"and estimated survival is "
        f"{latest['estimated_survival_pct']}%. "
        f"Overall status: {status}."
    )

    # --------------------------------------------------------
    # Return structured result
    # --------------------------------------------------------

    return {
        "type": "analysis",
        "response": summary,

        "analysis": {
            "pond_code": pond_code,

            "status": status,

            "latest_growth": {
                "date": str(
                    latest["sampling_date"]
                ),
                "doc": latest["doc"],
                "abw": float(
                    latest["avg_weight_g"]
                ),
                "biomass": float(
                    latest["biomass_kg"]
                ),
                "adg": float(
                    latest["adg_g"]
                ),
                "survival": float(
                    latest["estimated_survival_pct"]
                )
            },

            "latest_water": (
                {
                    "date": str(
                        water["measurement_date"]
                    ),
                    "doc": water["doc"],
                    "temperature": float(
                        water["temperature_c"]
                    ),
                    "ph": float(
                        water["ph"]
                    ),
                    "do": float(
                        water["dissolved_oxygen"]
                    ),
                    "salinity": float(
                        water["salinity_ppt"]
                    ),
                    "ammonia": float(
                        water["ammonia_mg_l"]
                    )
                }
                if water
                else None
            ),

            "feed_records": feed,

            "findings": findings
        }
    }