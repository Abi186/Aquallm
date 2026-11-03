"""Deterministic, read-only SQL question engine for AquaLLM.

The database calculates facts. Ollama may optionally turn the returned rows into
natural language, but it is never asked to invent or execute SQL.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

from sqlalchemy import text, bindparam
from sqlalchemy.orm import Session


# Conversation state is deliberately small and keyed by a frontend-generated ID.
# For multi-worker/production deployments, move this state to Redis or PostgreSQL.
CONVERSATIONS: dict[str, dict[str, Any]] = {}


def _rows(db: Session, sql: str, params: dict | None = None) -> list[dict]:
    statement = text(sql)
    for key, value in (params or {}).items():
        if isinstance(value, (tuple, list, set)):
            statement = statement.bindparams(bindparam(key, expanding=True))
    result = db.execute(statement, params or {})
    return [dict(row._mapping) for row in result]


def _one(db: Session, sql: str, params: dict | None = None) -> dict | None:
    statement = text(sql)
    for key, value in (params or {}).items():
        if isinstance(value, (tuple, list, set)):
            statement = statement.bindparams(bindparam(key, expanding=True))
    result = db.execute(statement, params or {}).fetchone()
    return dict(result._mapping) if result else None


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "Not available"
    if isinstance(value, float):
        return f"{value:,.{digits}f}"
    try:
        # Decimal values from PostgreSQL
        if value.__class__.__name__ == "Decimal":
            return f"{float(value):,.{digits}f}"
    except Exception:
        pass
    return str(value)


def _table(title: str, rows: list[dict], columns: list[tuple[str, str, str | None]]) -> str:
    if not rows:
        return f"{title}\nNo matching records were found in the database."
    lines = [title]
    headers = [label for _, label, _ in columns]
    lines.append(" | ".join(headers))
    lines.append(" | ".join("---" for _ in headers))
    for row in rows:
        values = []
        for key, _, unit in columns:
            value = row.get(key)
            rendered = _fmt(value)
            if value is not None and unit:
                rendered += f" {unit}"
            values.append(rendered)
        lines.append(" | ".join(values))
    lines.append(f"\nRecords returned: {len(rows)}. Source: AquaLLM PostgreSQL database.")
    return "\n".join(lines)


def _pond_ids_from_question(q: str, db: Session, previous: dict) -> list[int]:
    """Resolve Pond 101, pond ID 101, or a full pond code such as F01-P03."""
    code_match = re.search(r"\bF\d{1,3}\s*[-_]\s*P\d{1,3}\b", q, re.I)
    if code_match:
        code = re.sub(r"\s+", "", code_match.group(0)).replace("_", "-").upper()
        found = _rows(db, "SELECT pond_id FROM ponds WHERE UPPER(pond_code)=:code", {"code": code})
        return [found[0]["pond_id"]] if found else []

    # Explicit numeric pond reference. In this schema, Pond N means pond_id N.
    numeric = re.search(r"\bpond\s*(?:id\s*)?#?\s*(\d+)\b", q, re.I)
    if numeric:
        pond_id = int(numeric.group(1))
        found = _rows(db, "SELECT pond_id FROM ponds WHERE pond_id=:pid", {"pid": pond_id})
        if found:
            return [pond_id]
        # Permit a pond_code that is literally a numeric code if one exists.
        found = _rows(db, "SELECT pond_id FROM ponds WHERE pond_code=:code", {"code": numeric.group(1)})
        return [found[0]["pond_id"]] if found else []

    short = re.search(r"\bP\s*0*(\d+)\b", q, re.I)
    if short:
        code = f"P{int(short.group(1)):02d}"
        found = _rows(db, "SELECT pond_id FROM ponds WHERE UPPER(pond_code) LIKE :suffix", {"suffix": f"%-{code}"})
        if len(found) == 1:
            return [found[0]["pond_id"]]
        if len(found) > 1:
            return [r["pond_id"] for r in found]

    return list(previous.get("pond_ids", []))


def _resolve_named_ponds(q: str, db: Session) -> list[int]:
    matches = re.findall(r"\bpond\s*(?:id\s*)?#?\s*(\d+)\b", q, re.I)
    ids = []
    for number in matches:
        row = _one(db, "SELECT pond_id FROM ponds WHERE pond_id=:pid", {"pid": int(number)})
        if row:
            ids.append(row["pond_id"])
    codes = re.findall(r"\bF\d{1,3}\s*[-_]\s*P\d{1,3}\b", q, re.I)
    for raw in codes:
        code = re.sub(r"\s+", "", raw).replace("_", "-").upper()
        row = _one(db, "SELECT pond_id FROM ponds WHERE UPPER(pond_code)=:code", {"code": code})
        if row:
            ids.append(row["pond_id"])
    return list(dict.fromkeys(ids))


def _pond_filter(ids: list[int], alias: str = "p") -> tuple[str, dict]:
    if not ids:
        return "", {}
    # SQLAlchemy expanding bind parameter keeps this parameterized.
    return f" AND {alias}.pond_id IN :pond_ids", {"pond_ids": tuple(ids)}


def answer_database_question(question: str, db: Session, session_id: str = "default") -> tuple[str, bool]:
    q = question.lower().strip()
    state = CONVERSATIONS.setdefault(session_id, {"pond_ids": [], "last_result_ids": [], "last_intent": None})

    # If this is a follow-up with pronouns, inherit the most recent result set.
    explicit_ids = _resolve_named_ponds(q, db)
    pronoun_followup = bool(re.search(r"\b(it|its|them|their|those|these|among them|same ponds)\b", q))
    if explicit_ids:
        pond_ids = explicit_ids
    elif pronoun_followup and state.get("last_result_ids"):
        pond_ids = list(state["last_result_ids"])
    else:
        pond_ids = _pond_ids_from_question(q, db, state)

    # POND QUERIES ---------------------------------------------------------
    if any(x in q for x in ["how many ponds", "number of ponds", "total ponds", "pond count", "registered ponds", "ponds are registered"]):
        row = _one(db, "SELECT COUNT(*) AS pond_count FROM ponds")
        state.update(last_result_ids=[], last_intent="pond_count")
        return f"There are {row['pond_count']} ponds registered in the database.", True

    if "list all" in q and "pond" in q or "available pond ids" in q or "pond ids" in q:
        rows = _rows(db, "SELECT pond_id, pond_code FROM ponds ORDER BY pond_id")
        state.update(last_result_ids=[r['pond_id'] for r in rows], last_intent="pond_list")
        return _table("Registered pond IDs", rows, [("pond_id", "Pond ID", None), ("pond_code", "Pond code", None)]), True

    if "active" in q and "pond" in q:
        rows = _rows(db, "SELECT pond_id, pond_code, status FROM ponds WHERE LOWER(TRIM(status))='active' ORDER BY pond_id")
        state.update(last_result_ids=[r['pond_id'] for r in rows], last_intent="active_ponds")
        return f"Active ponds: {len(rows)}\n" + _table("Active pond details", rows, [("pond_id", "Pond ID", None), ("pond_code", "Pond", None), ("status", "Status", None)]), True

    if "pond" in q and any(x in q for x in ["highest doc", "maximum doc", "max doc", "doc greater", "doc above", "doc over"]):
        where = "WHERE g.doc > :threshold" if any(x in q for x in ["greater", "above", "over"]) else ""
        threshold_match = re.search(r"(?:greater than|above|over)\s*(\d+)", q)
        params = {"threshold": int(threshold_match.group(1))} if threshold_match else {}
        rows = _rows(db, f"""WITH latest AS (
            SELECT DISTINCT ON (pond_id) pond_id, doc, sampling_date FROM growth_sampling
            ORDER BY pond_id, sampling_date DESC, sampling_id DESC
        ) SELECT p.pond_id, p.pond_code, g.doc, g.sampling_date
          FROM latest g JOIN ponds p ON p.pond_id=g.pond_id {where}
          ORDER BY g.doc DESC NULLS LAST""", params)
        if "highest" in q or "maximum" in q or "max doc" in q:
            rows = rows[:1]
        state.update(last_result_ids=[r['pond_id'] for r in rows], last_intent="doc_ponds")
        return _table("Pond DOC results (latest growth sampling per pond)", rows, [("pond_id", "Pond ID", None), ("pond_code", "Pond", None), ("doc", "DOC", "days"), ("sampling_date", "Sampling date", None)]), True

    if "highest biomass" in q and not pond_ids:
        rows = _rows(db, """WITH latest AS (SELECT DISTINCT ON(pond_id) * FROM growth_sampling ORDER BY pond_id,sampling_date DESC,sampling_id DESC)
            SELECT p.pond_id,p.pond_code,p.farm_id,p.area_acres,p.culture_type,p.status,l.doc,l.avg_weight_g,l.biomass_kg,l.sampling_date
            FROM latest l JOIN ponds p ON p.pond_id=l.pond_id ORDER BY l.biomass_kg DESC NULLS LAST LIMIT 1""")
        state.update(last_result_ids=[r['pond_id'] for r in rows],last_intent="highest_biomass_pond")
        return _table("Pond details for the pond with the highest latest biomass", rows, [("pond_id","Pond ID",None),("pond_code","Pond",None),("farm_id","Farm ID",None),("area_acres","Area","acres"),("culture_type","Culture",None),("status","Status",None),("doc","DOC",None),("avg_weight_g","ABW","g"),("biomass_kg","Biomass","kg"),("sampling_date","Date",None)]), True

    if "pond" in q and ("detail" in q or "information" in q or "show pond" in q):
        if not pond_ids:
            return "I couldn't find that pond in the ponds table. Please check the pond ID or pond code (for example F01-P03).", True
        rows = _rows(db, """SELECT p.pond_id,p.pond_code,p.farm_id,p.area_acres,p.culture_type,p.status,
            g.doc,g.avg_weight_g,g.biomass_kg,g.sampling_date
            FROM ponds p LEFT JOIN LATERAL (SELECT doc,avg_weight_g,biomass_kg,sampling_date
              FROM growth_sampling WHERE pond_id=p.pond_id ORDER BY sampling_date DESC,sampling_id DESC LIMIT 1) g ON TRUE
            WHERE p.pond_id IN :ids ORDER BY p.pond_id""", {"ids": tuple(pond_ids)})
        state.update(pond_ids=pond_ids, last_result_ids=pond_ids, last_intent="pond_details")
        return _table("Pond details (latest growth values where available)", rows, [("pond_id","Pond ID",None),("pond_code","Pond",None),("farm_id","Farm ID",None),("area_acres","Area","acres"),("culture_type","Culture",None),("status","Status",None),("doc","Latest DOC","days"),("avg_weight_g","Latest ABW","g"),("biomass_kg","Latest biomass","kg")]), True

    # FOLLOW-UP: answer a field question about previous pond(s).
    if pronoun_followup and pond_ids and any(x in q for x in ["biomass", "abw", "body weight", "feed quantity", "feed", "doc", "details"]):
        if "biomass" in q:
            rows = _rows(db, """SELECT p.pond_id,p.pond_code,g.biomass_kg,g.sampling_date FROM ponds p
                LEFT JOIN LATERAL (SELECT biomass_kg,sampling_date FROM growth_sampling WHERE pond_id=p.pond_id ORDER BY sampling_date DESC,sampling_id DESC LIMIT 1) g ON TRUE
                WHERE p.pond_id IN :ids ORDER BY g.biomass_kg DESC NULLS LAST""", {"ids": tuple(pond_ids)})
            return _table("Latest biomass for the previously discussed pond(s)", rows, [("pond_code","Pond",None),("biomass_kg","Biomass","kg"),("sampling_date","Date",None)]), True
        if "feed" in q:
            rows = _rows(db, """SELECT p.pond_code,COALESCE(SUM(f.feed_quantity_kg),0) AS total_feed
                FROM ponds p LEFT JOIN feed_records f ON f.pond_id=p.pond_id WHERE p.pond_id IN :ids
                GROUP BY p.pond_id,p.pond_code ORDER BY total_feed DESC""", {"ids": tuple(pond_ids)})
            return _table("Feed quantities for the previously identified pond(s)", rows, [("pond_code","Pond",None),("total_feed","Total feed","kg")]), True

    # FEED QUERIES ---------------------------------------------------------
    if "feed" in q or "feeding" in q:
        if "yesterday" in q:
            rows = _rows(db, """SELECT p.pond_code, SUM(f.feed_quantity_kg) total_feed
                FROM feed_records f JOIN ponds p ON p.pond_id=f.pond_id
                WHERE f.feed_date=CURRENT_DATE-INTERVAL '1 day' GROUP BY p.pond_id,p.pond_code ORDER BY p.pond_code""")
            return _table("Feed given yesterday (database current date)", rows, [("pond_code","Pond",None),("total_feed","Feed","kg")]), True
        if "last 7 days" in q or "last seven days" in q or "daily feed consumption trend" in q:
            rows = _rows(db, """SELECT f.feed_date,p.pond_code,SUM(f.feed_quantity_kg) feed_kg
                FROM feed_records f JOIN ponds p ON p.pond_id=f.pond_id
                WHERE f.feed_date >= CURRENT_DATE-INTERVAL '6 days' AND f.feed_date < CURRENT_DATE+INTERVAL '1 day'
                GROUP BY f.feed_date,p.pond_id,p.pond_code ORDER BY f.feed_date,p.pond_code""")
            return _table("Daily feed trend for the last 7 calendar days", rows, [("feed_date","Date",None),("pond_code","Pond",None),("feed_kg","Feed","kg")]), True
        if "increased" in q and "previous day" in q:
            rows = _rows(db, """WITH daily AS (SELECT pond_id,feed_date,SUM(feed_quantity_kg) qty FROM feed_records GROUP BY pond_id,feed_date),
                ranked AS (SELECT *,LAG(qty) OVER(PARTITION BY pond_id ORDER BY feed_date) previous_qty,
                LAG(feed_date) OVER(PARTITION BY pond_id ORDER BY feed_date) previous_date FROM daily)
                SELECT p.pond_code,r.feed_date,r.qty,r.previous_date,r.previous_qty FROM ranked r JOIN ponds p ON p.pond_id=r.pond_id
                WHERE r.previous_qty IS NOT NULL AND r.qty>r.previous_qty ORDER BY r.feed_date DESC,p.pond_code""")
            state.update(last_result_ids=[r['pond_id'] for r in rows] if rows and 'pond_id' in rows[0] else [], last_intent="feed_increase")
            return _table("Ponds whose feed increased versus their previous recorded feed day", rows, [("pond_code","Pond",None),("previous_date","Previous date",None),("previous_qty","Previous feed","kg"),("feed_date","Current date",None),("qty","Current feed","kg")]), True
        if "top 5" in q and ("biomass" in q):
            rows = _rows(db, """WITH latest AS (SELECT DISTINCT ON(pond_id) pond_id,biomass_kg FROM growth_sampling ORDER BY pond_id,sampling_date DESC,sampling_id DESC),
                feeds AS (SELECT pond_id,SUM(feed_quantity_kg) total_feed FROM feed_records GROUP BY pond_id)
                SELECT p.pond_id,p.pond_code,l.biomass_kg,COALESCE(f.total_feed,0) total_feed FROM latest l JOIN ponds p ON p.pond_id=l.pond_id
                LEFT JOIN feeds f ON f.pond_id=p.pond_id ORDER BY l.biomass_kg DESC NULLS LAST LIMIT 5""")
            state.update(last_result_ids=[r['pond_id'] for r in rows], last_intent="top_biomass_feed")
            return _table("Top 5 ponds by latest biomass and total recorded feed", rows, [("pond_code","Pond",None),("biomass_kg","Latest biomass","kg"),("total_feed","Total feed","kg")]), True
        if "top 5" in q or "top five" in q:
            rows = _rows(db, """SELECT p.pond_id,p.pond_code,SUM(f.feed_quantity_kg) total_feed FROM feed_records f
                JOIN ponds p ON p.pond_id=f.pond_id GROUP BY p.pond_id,p.pond_code ORDER BY total_feed DESC LIMIT 5""")
            state.update(last_result_ids=[r['pond_id'] for r in rows], last_intent="top5_feed")
            return _table("Top 5 ponds by total feed consumption", rows, [("pond_code","Pond",None),("total_feed","Total feed","kg")]), True
        if pronoun_followup and pond_ids and "average" in q:
            row = _one(db, """SELECT AVG(x.total_feed) avg_feed FROM (SELECT pond_id,SUM(feed_quantity_kg) total_feed
                FROM feed_records WHERE pond_id IN :ids GROUP BY pond_id) x""", {"ids": tuple(pond_ids)})
            return f"Average total feed among the previously identified {len(pond_ids)} ponds: {_fmt(row['avg_feed'])} kg per pond.", True
        if "compare" in q and len(pond_ids) >= 2:
            rows = _rows(db, """SELECT p.pond_code,COALESCE(SUM(f.feed_quantity_kg),0) total_feed,
                COALESCE(AVG(f.feed_quantity_kg),0) avg_record_feed FROM ponds p LEFT JOIN feed_records f ON f.pond_id=p.pond_id
                WHERE p.pond_id IN :ids GROUP BY p.pond_id,p.pond_code ORDER BY p.pond_code""", {"ids": tuple(pond_ids)})
            state.update(last_result_ids=pond_ids,last_intent="feed_compare")
            return _table("Feed consumption comparison", rows, [("pond_code","Pond",None),("total_feed","Total feed","kg"),("avg_record_feed","Average feed record","kg")]), True
        if pond_ids and ("history" in q or "details" in q):
            rows = _rows(db, """SELECT p.pond_code,f.feed_date,f.doc,f.feed_type,f.feed_quantity_kg,f.feeding_frequency
                FROM feed_records f JOIN ponds p ON p.pond_id=f.pond_id WHERE f.pond_id IN :ids
                ORDER BY f.feed_date DESC LIMIT 100""", {"ids": tuple(pond_ids)})
            state.update(pond_ids=pond_ids,last_result_ids=pond_ids,last_intent="feed_history")
            return _table("Feed history", rows, [("pond_code","Pond",None),("feed_date","Date",None),("doc","DOC",None),("feed_type","Feed type",None),("feed_quantity_kg","Quantity","kg"),("feeding_frequency","Frequency","times/day")]), True
        if "highest" in q or "most" in q or "maximum" in q or "which pond" in q and "consum" in q:
            rows = _rows(db, """SELECT p.pond_id,p.pond_code,SUM(f.feed_quantity_kg) total_feed FROM feed_records f
                JOIN ponds p ON p.pond_id=f.pond_id GROUP BY p.pond_id,p.pond_code ORDER BY total_feed DESC LIMIT 1""")
            return _table("Pond with the highest total feed consumption", rows, [("pond_code","Pond",None),("total_feed","Total feed","kg")]), True
        if "more than 50" in q or "above 50" in q or "over 50" in q:
            rows = _rows(db, """SELECT p.pond_code,f.feed_date,SUM(f.feed_quantity_kg) feed_quantity_kg
                FROM feed_records f JOIN ponds p ON p.pond_id=f.pond_id
                GROUP BY p.pond_id,p.pond_code,f.feed_date HAVING SUM(f.feed_quantity_kg)>50
                ORDER BY feed_quantity_kg DESC""")
            return _table("Ponds with more than 50 kg total feed on a recorded day", rows, [("pond_code","Pond",None),("feed_date","Date",None),("feed_quantity_kg","Daily feed","kg")]), True
        if "average" in q or "avg" in q:
            row = _one(db, "SELECT AVG(day_total) avg_feed FROM (SELECT feed_date,SUM(feed_quantity_kg) day_total FROM feed_records GROUP BY feed_date) d")
            return f"Average daily feed consumption across all ponds (average of each recorded calendar day's total): {_fmt(row['avg_feed'])} kg/day.", True
        if "total" in q or "across all" in q or "all ponds" in q:
            row = _one(db, "SELECT SUM(feed_quantity_kg) total_feed FROM feed_records")
            return f"Total recorded feed quantity across all ponds: {_fmt(row['total_feed'])} kg.", True

    # GROWTH / BIOMASS -----------------------------------------------------
    if any(x in q for x in ["growth", "body weight", "abw", "biomass", "average doc", "below 10 grams"]):
        if "history" in q or "trend" in q:
            if not pond_ids:
                return "Please specify a pond ID or code for its growth history.", True
            rows = _rows(db, """SELECT p.pond_code,g.sampling_date,g.doc,g.avg_weight_g,g.biomass_kg,g.adg_g,g.estimated_survival_pct
                FROM growth_sampling g JOIN ponds p ON p.pond_id=g.pond_id WHERE g.pond_id IN :ids
                ORDER BY g.sampling_date DESC LIMIT 100""", {"ids": tuple(pond_ids)})
            state.update(pond_ids=pond_ids,last_result_ids=pond_ids,last_intent="growth_history")
            return _table("Growth history", rows, [("pond_code","Pond",None),("sampling_date","Date",None),("doc","DOC",None),("avg_weight_g","ABW","g"),("biomass_kg","Biomass","kg"),("adg_g","ADG","g/day"),("estimated_survival_pct","Survival","%")]), True
        if "below 10" in q or "less than 10" in q:
            rows = _rows(db, """WITH latest AS (SELECT DISTINCT ON(pond_id) pond_id,avg_weight_g,sampling_date FROM growth_sampling ORDER BY pond_id,sampling_date DESC,sampling_id DESC)
                SELECT p.pond_code,l.avg_weight_g,l.sampling_date FROM latest l JOIN ponds p ON p.pond_id=l.pond_id WHERE l.avg_weight_g<10 ORDER BY l.avg_weight_g""")
            state.update(last_result_ids=[r['pond_id'] for r in rows] if rows and 'pond_id' in rows[0] else [],last_intent="low_abw")
            return _table("Ponds with latest average body weight below 10 g", rows, [("pond_code","Pond",None),("avg_weight_g","ABW","g"),("sampling_date","Date",None)]), True
        if "average doc" in q:
            row = _one(db, """SELECT AVG(doc) avg_doc FROM (SELECT DISTINCT ON(pond_id) doc FROM growth_sampling ORDER BY pond_id,sampling_date DESC,sampling_id DESC) x""")
            return f"Average latest DOC across ponds with growth records: {_fmt(row['avg_doc'])} days.", True
        if "average" in q and ("weight" in q or "abw" in q):
            row = _one(db, """SELECT AVG(avg_weight_g) avg_weight FROM (SELECT DISTINCT ON(pond_id) avg_weight_g FROM growth_sampling ORDER BY pond_id,sampling_date DESC,sampling_id DESC) x""")
            return f"Average latest shrimp body weight across ponds with growth records: {_fmt(row['avg_weight'])} g.", True
        if "all ponds" in q and "biomass" in q or "biomass details" in q:
            rows = _rows(db, """SELECT p.pond_code,g.biomass_kg,g.doc,g.sampling_date FROM ponds p LEFT JOIN LATERAL
                (SELECT biomass_kg,doc,sampling_date FROM growth_sampling WHERE pond_id=p.pond_id ORDER BY sampling_date DESC,sampling_id DESC LIMIT 1) g ON TRUE ORDER BY g.biomass_kg DESC NULLS LAST""")
            state.update(last_result_ids=[r['pond_id'] for r in rows] if rows and 'pond_id' in rows[0] else [],last_intent="biomass_all")
            return _table("Latest biomass details for all ponds", rows, [("pond_code","Pond",None),("biomass_kg","Biomass","kg"),("doc","DOC",None),("sampling_date","Date",None)]), True
        if "highest" in q or "maximum" in q or "most" in q:
            rows = _rows(db, """WITH latest AS (SELECT DISTINCT ON(pond_id) * FROM growth_sampling ORDER BY pond_id,sampling_date DESC,sampling_id DESC)
                SELECT p.pond_code,l.biomass_kg,l.avg_weight_g,l.doc,l.sampling_date FROM latest l JOIN ponds p ON p.pond_id=l.pond_id
                ORDER BY l.biomass_kg DESC NULLS LAST LIMIT 1""") if "biomass" in q else _rows(db, """WITH latest AS (SELECT DISTINCT ON(pond_id) * FROM growth_sampling ORDER BY pond_id,sampling_date DESC,sampling_id DESC)
                SELECT p.pond_code,l.avg_weight_g,l.sampling_date FROM latest l JOIN ponds p ON p.pond_id=l.pond_id ORDER BY l.avg_weight_g DESC LIMIT 1""")
            return _table("Highest biomass pond" if "biomass" in q else "Pond with highest latest average body weight", rows, [("pond_code","Pond",None),("biomass_kg","Biomass","kg"),("avg_weight_g","ABW","g"),("doc","DOC",None),("sampling_date","Date",None)] if "biomass" in q else [("pond_code","Pond",None),("avg_weight_g","ABW","g"),("sampling_date","Date",None)]), True

    # WATER QUALITY -------------------------------------------------------
    if any(x in q for x in ["water quality", "dissolved oxygen", "oxygen", "temperature", "ph", "salinity", "ammonia"]):
        if "history" in q or "trend" in q:
            if not pond_ids:
                return "Please specify a pond ID or code for water-quality history.", True
            rows = _rows(db, """SELECT p.pond_code,w.measurement_date,w.doc,w.temperature_c,w.ph,w.dissolved_oxygen,w.salinity_ppt,w.ammonia_mg_l
                FROM water_quality w JOIN ponds p ON p.pond_id=w.pond_id WHERE w.pond_id IN :ids ORDER BY w.measurement_date DESC LIMIT 100""", {"ids": tuple(pond_ids)})
            state.update(pond_ids=pond_ids,last_result_ids=pond_ids,last_intent="water_history")
            return _table("Water-quality history", rows, [("pond_code","Pond",None),("measurement_date","Date",None),("doc","DOC",None),("temperature_c","Temperature","°C"),("ph","pH",None),("dissolved_oxygen","DO","mg/L"),("salinity_ppt","Salinity","ppt"),("ammonia_mg_l","Ammonia","mg/L")]), True
        if "compare" in q and len(pond_ids) >= 2:
            rows = _rows(db, """SELECT p.pond_code,w.measurement_date,w.temperature_c,w.ph,w.dissolved_oxygen,w.salinity_ppt,w.ammonia_mg_l
                FROM water_quality w JOIN ponds p ON p.pond_id=w.pond_id WHERE w.pond_id IN :ids
                AND (w.pond_id,w.measurement_date) IN (SELECT pond_id,MAX(measurement_date) FROM water_quality WHERE pond_id IN :ids GROUP BY pond_id)
                ORDER BY p.pond_code""", {"ids": tuple(pond_ids)})
            state.update(last_result_ids=pond_ids,last_intent="water_compare")
            return _table("Latest water-quality comparison", rows, [("pond_code","Pond",None),("measurement_date","Date",None),("temperature_c","Temp","°C"),("ph","pH",None),("dissolved_oxygen","DO","mg/L"),("salinity_ppt","Salinity","ppt"),("ammonia_mg_l","Ammonia","mg/L")]), True
        if "missing" in q:
            rows = _rows(db, """SELECT p.pond_id,p.pond_code FROM ponds p LEFT JOIN water_quality w ON w.pond_id=p.pond_id
                WHERE w.water_id IS NULL ORDER BY p.pond_id""")
            state.update(last_result_ids=[r['pond_id'] for r in rows],last_intent="missing_water")
            return _table("Ponds with no water-quality records", rows, [("pond_id","Pond ID",None),("pond_code","Pond",None)]), True
        if ("below 4" in q or "low dissolved" in q or "low do" in q) and ("above 30" in q or "over 30" in q):
            rows = _rows(db, """WITH latest AS (SELECT DISTINCT ON(pond_id) pond_id,dissolved_oxygen,temperature_c,measurement_date
                FROM water_quality ORDER BY pond_id,measurement_date DESC,water_id DESC)
                SELECT p.pond_id,p.pond_code,l.dissolved_oxygen,l.temperature_c,l.measurement_date FROM latest l
                JOIN ponds p ON p.pond_id=l.pond_id WHERE l.dissolved_oxygen<4 AND l.temperature_c>30
                ORDER BY l.dissolved_oxygen,l.temperature_c DESC""")
            state.update(last_result_ids=[r['pond_id'] for r in rows],last_intent="critical_water")
            return _table("Ponds with latest DO below 4 mg/L AND temperature above 30°C", rows, [("pond_id","Pond ID",None),("pond_code","Pond",None),("dissolved_oxygen","DO","mg/L"),("temperature_c","Temperature","°C"),("measurement_date","Date",None)]), True
        if "how many" in q and ("low" in q or "oxygen" in q):
            row = _one(db, """SELECT COUNT(*) pond_count FROM (SELECT DISTINCT ON(pond_id) pond_id,dissolved_oxygen FROM water_quality ORDER BY pond_id,measurement_date DESC,water_id DESC) x WHERE dissolved_oxygen<4""")
            return f"{row['pond_count']} ponds currently have a latest recorded dissolved oxygen level below 4 mg/L.", True
        if "below 4" in q or "low dissolved" in q or "low do" in q:
            rows = _rows(db, """WITH latest AS (SELECT DISTINCT ON(pond_id) pond_id,dissolved_oxygen,measurement_date FROM water_quality ORDER BY pond_id,measurement_date DESC,water_id DESC)
                SELECT p.pond_id,p.pond_code,l.dissolved_oxygen,l.measurement_date FROM latest l JOIN ponds p ON p.pond_id=l.pond_id WHERE l.dissolved_oxygen<4 ORDER BY l.dissolved_oxygen""")
            state.update(last_result_ids=[r['pond_id'] for r in rows],last_intent="low_do")
            return _table("Ponds with latest DO below 4 mg/L", rows, [("pond_id","Pond ID",None),("pond_code","Pond",None),("dissolved_oxygen","DO","mg/L"),("measurement_date","Date",None)]), True
        if "above 30" in q or "over 30" in q or "above 30°" in q:
            rows = _rows(db, """WITH latest AS (SELECT DISTINCT ON(pond_id) pond_id,temperature_c,measurement_date FROM water_quality ORDER BY pond_id,measurement_date DESC,water_id DESC)
                SELECT p.pond_code,l.temperature_c,l.measurement_date FROM latest l JOIN ponds p ON p.pond_id=l.pond_id WHERE l.temperature_c>30 ORDER BY l.temperature_c DESC""")
            state.update(last_result_ids=[r['pond_id'] for r in rows],last_intent="high_temp")
            return _table("Ponds with latest temperature above 30°C", rows, [("pond_code","Pond",None),("temperature_c","Temperature","°C"),("measurement_date","Date",None)]), True
        if "average" in q and "temperature" in q:
            row = _one(db, """SELECT AVG(temperature_c) avg_temp FROM (SELECT DISTINCT ON(pond_id) temperature_c FROM water_quality ORDER BY pond_id,measurement_date DESC,water_id DESC) x""")
            return f"Average latest water temperature across ponds with records: {_fmt(row['avg_temp'])} °C.", True
        if "highest" in q and "temperature" in q:
            rows = _rows(db, """WITH latest AS (SELECT DISTINCT ON(pond_id) pond_id,temperature_c,measurement_date FROM water_quality ORDER BY pond_id,measurement_date DESC,water_id DESC)
                SELECT p.pond_code,l.temperature_c,l.measurement_date FROM latest l JOIN ponds p ON p.pond_id=l.pond_id ORDER BY l.temperature_c DESC LIMIT 1""")
            return _table("Pond with highest latest temperature", rows, [("pond_code","Pond",None),("temperature_c","Temperature","°C"),("measurement_date","Date",None)]), True

    # ADVANCED MULTI-TABLE QUERIES ----------------------------------------
    if "high biomass" in q and ("low feed" in q or "relatively" in q):
        rows = _rows(db, """WITH g AS (SELECT DISTINCT ON(pond_id) pond_id,biomass_kg FROM growth_sampling ORDER BY pond_id,sampling_date DESC,sampling_id DESC),
            f AS (SELECT pond_id,AVG(feed_quantity_kg) avg_feed FROM feed_records GROUP BY pond_id),
            averages AS (SELECT AVG(biomass_kg) avg_biomass FROM g), fa AS (SELECT AVG(avg_feed) avg_feed FROM f)
            SELECT p.pond_code,g.biomass_kg,f.avg_feed FROM g JOIN f ON f.pond_id=g.pond_id JOIN ponds p ON p.pond_id=g.pond_id,averages,fa
            WHERE g.biomass_kg>averages.avg_biomass AND f.avg_feed<fa.avg_feed ORDER BY g.biomass_kg DESC""")
        state.update(last_result_ids=[],last_intent="high_biomass_low_feed")
        return _table("High-biomass ponds with below-average feed per feeding record", rows, [("pond_code","Pond",None),("biomass_kg","Biomass","kg"),("avg_feed","Average feed entry","kg")]), True

    if "doc range" in q or "doc ranges" in q or "different doc" in q:
        rows = _rows(db, """SELECT CASE WHEN doc<=30 THEN '0-30' WHEN doc<=60 THEN '31-60' WHEN doc<=90 THEN '61-90' ELSE '91+' END doc_range,
            AVG(feed_quantity_kg) avg_feed,SUM(feed_quantity_kg) total_feed,COUNT(*) feed_records FROM feed_records
            WHERE doc IS NOT NULL GROUP BY 1 ORDER BY MIN(doc)""")
        return _table("Feed consumption by DOC range", rows, [("doc_range","DOC range (days)",None),("avg_feed","Average feed","kg"),("total_feed","Total feed","kg"),("feed_records","Records",None)]), True

    if "relationship" in q and ("weight" in q or "abw" in q) and "feed" in q:
        rows = _rows(db, """WITH g AS (SELECT DISTINCT ON(pond_id) pond_id,avg_weight_g FROM growth_sampling ORDER BY pond_id,sampling_date DESC,sampling_id DESC),
            f AS (SELECT pond_id,AVG(feed_quantity_kg) avg_feed FROM feed_records GROUP BY pond_id)
            SELECT p.pond_code,g.avg_weight_g,f.avg_feed FROM g JOIN f ON f.pond_id=g.pond_id JOIN ponds p ON p.pond_id=g.pond_id ORDER BY g.avg_weight_g""")
        corr = _one(db, """WITH g AS (SELECT DISTINCT ON(pond_id) pond_id,avg_weight_g FROM growth_sampling ORDER BY pond_id,sampling_date DESC,sampling_id DESC),
            f AS (SELECT pond_id,AVG(feed_quantity_kg) avg_feed FROM feed_records GROUP BY pond_id)
            SELECT CORR(g.avg_weight_g,f.avg_feed) correlation FROM g JOIN f ON f.pond_id=g.pond_id""")
        return _table(f"Latest ABW versus average feed by pond (Pearson correlation: {_fmt(corr['correlation'],3)})", rows, [("pond_code","Pond",None),("avg_weight_g","Latest ABW","g"),("avg_feed","Average feed entry","kg")]), True

    # Generic follow-up: their feed quantities after a filter result.
    if pronoun_followup and pond_ids and "feed" in q:
        rows = _rows(db, """SELECT p.pond_code,COALESCE(SUM(f.feed_quantity_kg),0) total_feed FROM ponds p
            LEFT JOIN feed_records f ON f.pond_id=p.pond_id WHERE p.pond_id IN :ids GROUP BY p.pond_id,p.pond_code ORDER BY p.pond_code""", {"ids": tuple(pond_ids)})
        return _table("Feed quantities for the previously identified ponds", rows, [("pond_code","Pond",None),("total_feed","Total feed","kg")]), True

    # A specific pond context is remembered even if the next query is vague.
    if pond_ids:
        state["pond_ids"] = pond_ids
    return "", False
