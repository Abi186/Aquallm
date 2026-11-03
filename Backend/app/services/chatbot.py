
import re
import requests

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import (
    OLLAMA_GENERATE_URL,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_TIMEOUT,
)

from app.services.rag import (
    format_context,
    format_sources,
    retrieve,
)


# ============================================================
# OLLAMA CONFIGURATION
# ============================================================

OLLAMA_URL = OLLAMA_GENERATE_URL
MODEL_NAME = OLLAMA_MODEL


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are AquaLLM, an AI assistant for shrimp aquaculture.

You answer questions using actual AquaLLM PostgreSQL farm data.

AQUACULTURE DEFINITIONS:

ABW = Average Body Weight.
ADG = Average Daily Growth.
DOC = Days of Culture.
FCR = Feed Conversion Ratio.
DO = Dissolved Oxygen.

IMPORTANT RULES:

1. PostgreSQL is the source of truth for farm-specific data.
2. Never invent farm-specific values.
3. Never guess missing database values.
4. ABW means Average Body Weight.
5. Use exact pond codes supplied by the database.
6. Pond codes can look like F01-P01, F01-P02, F02-P03.
7. If a short pond code matches multiple ponds, ask for clarification.
8. Always include measurement units.
9. If a database record is unavailable, clearly say so.
10. Separate actual database values from general guidelines.
11. Keep answers simple, practical and concise.

DATABASE RETRIEVAL RULES:

12. Questions about all ponds do not require a specific pond code.
13. Questions about total counts, averages, maximums, minimums,
    rankings and comparisons should use the supplied SQL results.
14. Never ask for a pond code when the question concerns all ponds.
15. Never invent a database query result.
16. Use only the database context provided to answer farm questions.

KNOWLEDGE RULES:

17. AQUACULTURE KNOWLEDGE contains general reference guidelines.
18. It is not actual farm data.
19. Never present guideline values as actual pond measurements.
20. For general questions, use knowledge without asking for a pond code.
21. If information is unavailable, clearly explain that.

FOLLOW-UP RULES:

22. Maintain the pond context when answering follow-up questions.
23. Never change the pond unless the user specifies another pond.
"""


# ============================================================
# BUILD PROMPT
# ============================================================

def build_prompt(
    question: str,
    context: str = "",
    knowledge: str = ""
):

    return f"""
{SYSTEM_PROMPT}

============================================================
DATABASE INFORMATION
============================================================

{context}

============================================================
AQUACULTURE KNOWLEDGE
============================================================

{knowledge}

============================================================
USER QUESTION
============================================================

{question}

============================================================
ANSWER
============================================================

Answer the user's question using the supplied information.

For farm-specific questions, use actual database results.

For general aquaculture questions, use general knowledge.

Do not request a pond code for database-wide questions.

Never invent values.
"""


# ============================================================
# ASK OLLAMA
# ============================================================

def ask_ollama_ex(
    question: str,
    context: str = "",
    knowledge: str = ""
):

    prompt = build_prompt(
        question,
        context,
        knowledge
    )

    try:

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": MODEL_NAME,
                "prompt": prompt,
                "stream": False,
                "keep_alive": OLLAMA_KEEP_ALIVE,
                "options": {
                    "temperature": 0.1,
                    "num_ctx": OLLAMA_NUM_CTX
                }
            },
            timeout=OLLAMA_TIMEOUT
        )

        if response.status_code == 404:

            return (
                f"Model {MODEL_NAME} is not installed. "
                f"Run: ollama pull {MODEL_NAME}",
                False
            )

        response.raise_for_status()

        data = response.json()

        answer = data.get("response", "").strip()

        if not answer:
            return "AquaLLM could not generate a response.", False

        return answer, True

    except requests.exceptions.ConnectionError:

        return (
            "Cannot connect to Ollama. Check whether Ollama is running.",
            False
        )

    except requests.exceptions.Timeout:

        return (
            "Ollama request timed out. Please try again.",
            False
        )

    except Exception as e:

        return f"AquaLLM error: {str(e)}", False


def ask_ollama(
    question: str,
    context: str = "",
    knowledge: str = ""
):

    answer, _ok = ask_ollama_ex(
        question,
        context,
        knowledge
    )

    return answer


# ============================================================
# DATABASE-WIDE QUERY RETRIEVAL
# ============================================================

def get_global_database_context(
    question: str,
    db: Session
):

    q = question.lower().strip()

    # --------------------------------------------------------
    # TOTAL POND COUNT
    # --------------------------------------------------------

    count_keywords = [
        "how many ponds",
        "number of ponds",
        "total ponds",
        "pond count",
        "count of ponds",
        "registered ponds",
        "ponds registered",
        "unique ponds"
    ]

    if any(k in q for k in count_keywords):

        result = db.execute(
            text("""
                SELECT COUNT(DISTINCT pond_id)
                FROM ponds
            """)
        )

        count = result.scalar()

        return f"""
DATABASE QUERY RESULT:

Total registered ponds: {count}

Source: PostgreSQL ponds table.
SQL operation: COUNT(DISTINCT pond_id).

This is the actual database result.
"""


    # --------------------------------------------------------
    # AVERAGE FEED
    # --------------------------------------------------------

    if "average feed" in q or "avg feed" in q:

        result = db.execute(
            text("""
                SELECT AVG(feed_quantity_kg)
                FROM feed_records
            """)
        )

        value = result.scalar()

        return f"""
DATABASE QUERY RESULT:

Average feed quantity: {value} kg

Source: PostgreSQL feed_records table.
"""


    # --------------------------------------------------------
    # TOTAL FEED
    # --------------------------------------------------------

    if "total feed" in q or "overall feed" in q:

        result = db.execute(
            text("""
                SELECT SUM(feed_quantity_kg)
                FROM feed_records
            """)
        )

        value = result.scalar()

        return f"""
DATABASE QUERY RESULT:

Total feed quantity: {value} kg

Source: PostgreSQL feed_records table.
"""


    # --------------------------------------------------------
    # HIGHEST BIOMASS
    # --------------------------------------------------------

    if "highest biomass" in q or "maximum biomass" in q:

        result = db.execute(
            text("""
                SELECT
                    p.pond_code,
                    g.biomass_kg,
                    g.sampling_date
                FROM growth_sampling g
                JOIN ponds p
                    ON p.pond_id = g.pond_id
                WHERE g.biomass_kg IS NOT NULL
                ORDER BY g.biomass_kg DESC
                LIMIT 1
            """)
        )

        row = result.fetchone()

        if row:

            return f"""
DATABASE QUERY RESULT:

Pond: {row.pond_code}
Biomass: {row.biomass_kg} kg
Sampling date: {row.sampling_date}

Source: PostgreSQL growth_sampling table.
"""

        return "No biomass records found in the database."


    # --------------------------------------------------------
    # LOW DISSOLVED OXYGEN
    # --------------------------------------------------------

    if "low dissolved oxygen" in q or "do below" in q:

        result = db.execute(
            text("""
                SELECT
                    p.pond_code,
                    w.dissolved_oxygen,
                    w.measurement_date
                FROM water_quality w
                JOIN ponds p
                    ON p.pond_id = w.pond_id
                WHERE w.dissolved_oxygen < 4
                ORDER BY w.dissolved_oxygen ASC
            """)
        )

        rows = result.fetchall()

        if not rows:
            return "No ponds with dissolved oxygen below 4 mg/L were found."

        output = ["DATABASE QUERY RESULT: Ponds with DO below 4 mg/L"]

        for row in rows:

            output.append(
                f"Pond: {row.pond_code} | "
                f"DO: {row.dissolved_oxygen} mg/L | "
                f"Date: {row.measurement_date}"
            )

        return "\n".join(output)


    # --------------------------------------------------------
    # TOP 5 FEED CONSUMPTION
    # --------------------------------------------------------

    if (
        "top 5 ponds" in q
        and ("feed" in q or "consumption" in q)
    ):

        result = db.execute(
            text("""
                SELECT
                    p.pond_code,
                    SUM(f.feed_quantity_kg) AS total_feed
                FROM feed_records f
                JOIN ponds p
                    ON p.pond_id = f.pond_id
                GROUP BY p.pond_id, p.pond_code
                ORDER BY total_feed DESC
                LIMIT 5
            """)
        )

        rows = result.fetchall()

        if not rows:
            return "No feed records found."

        output = ["DATABASE QUERY RESULT: Top 5 ponds by feed consumption"]

        for row in rows:

            output.append(
                f"{row.pond_code}: {row.total_feed} kg"
            )

        return "\n".join(output)


    return None


# ============================================================
# FIND POND
# ============================================================

def find_pond(question: str, db: Session):

    question_lower = question.lower().strip()

    result = db.execute(
        text("""
            SELECT
                pond_id,
                pond_code,
                farm_id,
                area_acres,
                culture_type,
                status
            FROM ponds
            ORDER BY pond_id
        """)
    )

    ponds = [
        dict(row._mapping)
        for row in result
    ]

    # Exact full pond code

    for pond in ponds:

        pond_code = str(pond["pond_code"]).strip().lower()

        if pond_code and pond_code in question_lower:

            return {
                "status": "found",
                "pond": pond
            }

    # Short pond code

    short_match = re.search(
        r"\b(?:pond\s*)?(p\d+)\b",
        question_lower
    )

    if short_match:

        short_code = short_match.group(1).upper()

        matching_ponds = [
            pond for pond in ponds
            if str(pond["pond_code"]).strip().upper().endswith(
                "-" + short_code
            )
        ]

        if len(matching_ponds) == 1:

            return {
                "status": "found",
                "pond": matching_ponds[0]
            }

        if len(matching_ponds) > 1:

            return {
                "status": "ambiguous",
                "short_code": short_code,
                "ponds": matching_ponds
            }

    # Numeric pond ID

    number_match = re.search(
        r"\bpond\s*(\d+)\b",
        question_lower
    )

    if number_match:

        pond_number = int(number_match.group(1))

        for pond in ponds:

            if int(pond["pond_id"]) == pond_number:

                return {
                    "status": "found",
                    "pond": pond
                }

    return {"status": "not_found"}


# ============================================================
# POND CONTEXT
# ============================================================

def get_pond_context(pond, context_parts):

    context_parts.append(f"""
POND INFORMATION

Pond ID: {pond['pond_id']}
Pond Code: {pond['pond_code']}
Farm ID: {pond['farm_id']}
Area: {pond['area_acres']} acres
Culture Type: {pond['culture_type']}
Status: {pond['status']}
""")


# ============================================================
# LATEST GROWTH
# ============================================================

def get_latest_growth(pond_id: int, db: Session):

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
        {"pond_id": pond_id}
    )

    row = result.fetchone()

    return dict(row._mapping) if row else None


# ============================================================
# GROWTH HISTORY
# ============================================================

def get_growth_history(pond_id: int, db: Session):

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
            LIMIT 20
        """),
        {"pond_id": pond_id}
    )

    return [dict(row._mapping) for row in result]


# ============================================================
# LATEST WATER
# ============================================================

def get_latest_water(pond_id: int, db: Session):

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
        {"pond_id": pond_id}
    )

    row = result.fetchone()

    return dict(row._mapping) if row else None


# ============================================================
# WATER HISTORY
# ============================================================

def get_water_history(pond_id: int, db: Session):

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
            LIMIT 20
        """),
        {"pond_id": pond_id}
    )

    return [dict(row._mapping) for row in result]


# ============================================================
# FEED HISTORY
# ============================================================

def get_feed_history(pond_id: int, db: Session):

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
            LIMIT 20
        """),
        {"pond_id": pond_id}
    )

    return [dict(row._mapping) for row in result]


# ============================================================
# HARVEST HISTORY
# ============================================================

def get_harvest_history(pond_id: int, db: Session):

    result = db.execute(
        text("""
            SELECT
                harvest_date,
                harvest_quantity_kg,
                avg_weight_g,
                survival_pct,
                total_feed_kg,
                fcr
            FROM harvest_records
            WHERE pond_id = :pond_id
            ORDER BY harvest_date DESC
            LIMIT 20
        """),
        {"pond_id": pond_id}
    )

    return [dict(row._mapping) for row in result]


# ============================================================
# DATABASE CONTEXT
# ============================================================

def get_database_context(question: str, db: Session):

    question_lower = question.lower()

    # 1. Try database-wide retrieval FIRST.

    global_context = get_global_database_context(
        question,
        db
    )

    if global_context is not None:
        return global_context

    context_parts = []

    # 2. Find specific pond.

    pond_result = find_pond(question, db)

    if pond_result["status"] == "ambiguous":

        pond_codes = [
            pond["pond_code"]
            for pond in pond_result["ponds"]
        ]

        return (
            "AMBIGUOUS POND: "
            + ", ".join(pond_codes)
            + ". Please specify the complete pond code."
        )

    if pond_result["status"] == "not_found":

        return "NO SPECIFIC POND WAS IDENTIFIED."

    pond = pond_result["pond"]

    get_pond_context(pond, context_parts)

    pond_id = pond["pond_id"]

    # 3. Growth retrieval.

    growth_keywords = [
        "abw", "average body weight", "weight",
        "growth", "biomass", "adg", "survival", "doc"
    ]

    if any(k in question_lower for k in growth_keywords):

        record = get_latest_growth(pond_id, db)

        if record:

            context_parts.append(f"""
LATEST GROWTH RECORD

Date: {record['sampling_date']}
DOC: {record['doc']}
ABW: {record['avg_weight_g']} g
Biomass: {record['biomass_kg']} kg
ADG: {record['adg_g']} g/day
Survival: {record['estimated_survival_pct']} %
""")

        else:
            context_parts.append("No growth record found.")

    # Growth history.

    if any(k in question_lower for k in [
        "trend", "history", "progress", "over time"
    ]):

        records = get_growth_history(pond_id, db)

        for record in records:
            context_parts.append(str(record))

    # 4. Water retrieval.

    water_keywords = [
        "water", "do", "dissolved oxygen",
        "oxygen", "ph", "temperature",
        "salinity", "ammonia"
    ]

    if any(k in question_lower for k in water_keywords):

        record = get_latest_water(pond_id, db)

        if record:

            context_parts.append(f"""
LATEST WATER QUALITY

Date: {record['measurement_date']}
Temperature: {record['temperature_c']} °C
pH: {record['ph']}
DO: {record['dissolved_oxygen']} mg/L
Salinity: {record['salinity_ppt']} ppt
Ammonia: {record['ammonia_mg_l']} mg/L
""")

        else:
            context_parts.append("No water-quality record found.")

    if any(k in question_lower for k in [
        "water trend", "water history",
        "water quality trend", "water over time"
    ]):

        records = get_water_history(pond_id, db)

        for record in records:
            context_parts.append(str(record))

    # 5. Feed retrieval.

    feed_keywords = [
        "feed", "feeding", "fcr", "feed quantity"
    ]

    if any(k in question_lower for k in feed_keywords):

        records = get_feed_history(pond_id, db)

        if records:

            context_parts.append("\nFEED HISTORY\n")

            for record in records:
                context_parts.append(str(record))

        else:
            context_parts.append("No feed records found.")

    # 6. Harvest retrieval.

    if any(k in question_lower for k in [
        "harvest", "fcr", "survival"
    ]):

        records = get_harvest_history(pond_id, db)

        if records:

            context_parts.append("\nHARVEST HISTORY\n")

            for record in records:
                context_parts.append(str(record))

        else:
            context_parts.append("No harvest records found.")

    return "\n".join(context_parts)


# ============================================================
# KNOWLEDGE RETRIEVAL
# ============================================================

KNOWLEDGE_CUES = [
    "what is", "what are", "what does", "meaning",
    "define", "explain", "why", "how to", "how do",
    "how can", "how does", "cause", "reason",
    "ideal", "optimum", "optimal", "normal",
    "safe", "range", "good", "bad", "problem",
    "improve", "increase", "reduce", "decrease",
    "prevent", "solution", "fix", "symptom",
    "disease", "tip", "suggest", "recommend",
    "should", "formula", "calculate", "difference",
    "low", "high"
]


def wants_knowledge(question: str, context: str):

    q = question.lower()

    if "NO SPECIFIC POND" in context:
        return True

    return any(cue in q for cue in KNOWLEDGE_CUES)


# ============================================================
# MAIN AQUALLM FUNCTION
# ============================================================

def ask_aqua_llm(question: str, db: Session):

    # 1. Retrieve actual PostgreSQL data.

    context = get_database_context(
        question,
        db
    )

    # 2. Retrieve aquaculture knowledge if needed.

    chunks = []

    if wants_knowledge(question, context):

        chunks = retrieve(question)

    knowledge = format_context(chunks)

    # 3. Ask Ollama.

    answer, ok = ask_ollama_ex(
        question=question,
        context=context,
        knowledge=knowledge
    )

    # 4. Add knowledge sources.

    if ok and chunks:
        answer += "\n\n" + format_sources(chunks)

    return answer
