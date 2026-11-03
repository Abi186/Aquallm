# app/routes/chat.py

from typing import Optional, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db

from app.services.chatbot import ask_aqua_llm
from app.services.database_chat import answer_database_question

from app.services.analysis_engine import (
    analyze_question,
    find_analysis_pond,
    detect_analysis_type
)

from app.services.growth_analysis import (
    analyze_growth
)


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/api/chat",
    tags=["Chatbot"]
)


# ============================================================
# REQUEST MODEL
# ============================================================

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"


# ============================================================
# RESPONSE MODEL
# ============================================================

class ChatResponse(BaseModel):

    response: str

    type: str = "text"

    chart: Optional[Any] = None

    analysis: Optional[Any] = None


# ============================================================
# CHAT ENDPOINT
# ============================================================

@router.post(
    "/",
    response_model=ChatResponse
)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db)
):

    # --------------------------------------------------------
    # Clean question
    # --------------------------------------------------------

    question = request.message.strip()

    # Empty question protection
    if not question:

        return {
            "response": "Please enter a question.",
            "type": "text",
            "chart": None,
            "analysis": None
        }

    # --------------------------------------------------------
    # Detect question type
    # --------------------------------------------------------

    question_type = detect_analysis_type(
        question
    )

    # ========================================================
    # 1. GROWTH ANALYSIS / DIAGNOSIS
    # ========================================================
    #
    # Examples:
    #
    # Why is growth slow in F01-P03?
    # Is there a problem with growth in F01-P03?
    # Why is growth poor in F05-P03?
    #
    # ========================================================

    if question_type == "growth_analysis":

        pond_result = find_analysis_pond(
            question,
            db
        )

        # ----------------------------------------------------
        # Ambiguous pond
        # ----------------------------------------------------

        if pond_result["status"] == "ambiguous":

            codes = [
                pond["pond_code"]
                for pond in pond_result["ponds"]
            ]

            return {
                "response": (
                    "Multiple ponds match "
                    f"{pond_result['short_code']}: "
                    + ", ".join(codes)
                    + ". Please specify the complete pond code."
                ),
                "type": "text",
                "chart": None,
                "analysis": None
            }

        # ----------------------------------------------------
        # Pond not found
        # ----------------------------------------------------

        if pond_result["status"] == "not_found":

            return {
                "response": (
                    "I could not identify the pond. "
                    "Please provide the complete pond code, "
                    "for example F01-P03."
                ),
                "type": "text",
                "chart": None,
                "analysis": None
            }

        # ----------------------------------------------------
        # Pond found
        # ----------------------------------------------------

        pond = pond_result["pond"]

        result = analyze_growth(
            pond_id=pond["pond_id"],
            pond_code=pond["pond_code"],
            db=db
        )

        return {
            "response": result["response"],
            "type": result.get(
                "type",
                "analysis"
            ),
            "chart": result.get(
                "chart"
            ),
            "analysis": result.get(
                "analysis"
            )
        }

    # ========================================================
    # 2. TREND / CHART ANALYSIS
    # ========================================================
    #
    # Examples:
    #
    # Show ABW trend of F01-P03
    # Show growth trend of F01-P03
    # Show water quality trend of F01-P03
    # Show DO trend of F05-P03
    #
    # ========================================================

    analysis_result = analyze_question(
        question,
        db
    )

    # --------------------------------------------------------
    # If analysis_engine understood the question
    # --------------------------------------------------------

    if analysis_result is not None:

        return {
            "response": analysis_result["response"],
            "type": analysis_result.get(
                "type",
                "text"
            ),
            "chart": analysis_result.get(
                "chart"
            ),
            "analysis": None
        }

    # ========================================================
    # 3. STRUCTURED DATABASE QUESTION ENGINE
    # ========================================================
    # Handles pond/feed/growth/water-quality aggregates, filters,
    # comparisons, joins and conversation follow-ups using safe SQL.

    database_answer, handled = answer_database_question(
        question=question,
        db=db,
        session_id=request.session_id or "default"
    )

    if handled:
        return {
            "response": database_answer,
            "type": "text",
            "chart": None,
            "analysis": None
        }

    # ========================================================
    # 4. NORMAL LLM + DATABASE QUESTION
    # ========================================================
    #
    # Examples:
    #
    # What is the latest ABW of F01-P03?
    # What is the latest DO of F05-P03?
    # What is FCR?
    #
    # These are handled by chatbot.py
    #
    # ========================================================

    answer = ask_aqua_llm(
        question=question,
        db=db
    )

    return {
        "response": answer,
        "type": "text",
        "chart": None,
        "analysis": None
    }